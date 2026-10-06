"""Verify real link semantics, protected account changes and transport failure behavior."""

import json
import smtplib
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.account_models import AccountActionToken, AccountProfile, AccountSecurity, EmailOutbox
from backend.account_terms import TERMS_VERSION, require_current_terms
from backend.config import get_settings
from backend.database import Base, get_db
from backend.main import app
from backend.models import Account, AdminAccess, Application, Login, Session
from backend.services import account_mail, account_service
from backend.services.session_service import token_hash

PASSWORD = "private-test-password-123"
NEW_PASSWORD = "different-test-password-456"


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "account.db"), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    settings = get_settings()
    monkeypatch.setattr(settings, "hosted_ai_enabled", False)
    monkeypatch.setattr(settings, "site_url", "https://tafolliboost.com")
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.invalid")
    monkeypatch.setattr(settings, "smtp_username", "operator@example.invalid")
    monkeypatch.setattr(settings, "smtp_password", "synthetic-mail-password")
    monkeypatch.setattr(settings, "mail_transport", "smtp")
    monkeypatch.setattr(settings, "mail_key_file", str(tmp_path / "mail.key"))

    def db_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    yield TestClient(app), factory
    app.dependency_overrides.clear()
    engine.dispose()


def signup(client, email="alex@example.com", **extra):
    return client.post("/api/account/register", json={
        "email": email, "password": PASSWORD, "terms_accepted": True,
        "privacy_acknowledged": True, "terms_version": TERMS_VERSION,
        "display_name": "Alex", **extra,
    })


def latest_token(factory, email, purpose):
    with factory() as db:
        row = db.query(EmailOutbox).filter_by(recipient=email, purpose=purpose).order_by(EmailOutbox.created_at.desc()).first()
        return json.loads(account_mail.cipher().decrypt(row.payload_cipher.encode()))["token"]


def activate(client, factory, email="alex@example.com"):
    assert signup(client, email).status_code == 200
    assert client.post("/api/account/verify-email", json={"token": latest_token(factory, email, "verify")}).status_code == 200
    assert client.post("/api/account/login", json={"email": email, "password": PASSWORD}).status_code == 200


def test_registration_requires_consent_and_actual_mail_transport(lifecycle, monkeypatch):
    client, factory = lifecycle
    for extra in ({"terms_accepted": False}, {"privacy_acknowledged": False}, {"terms_version": "old"}):
        assert signup(client, **extra).status_code == 422
    monkeypatch.setattr(get_settings(), "smtp_enabled", False)
    response = signup(client)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MAIL_UNAVAILABLE"
    with factory() as db:
        assert db.query(Account).count() == 0


def test_pending_account_cannot_login_or_forge_cookie_and_link_is_single_use(lifecycle):
    client, factory = lifecycle
    response = signup(client)
    assert response.status_code == 200
    assert response.json()["verification_required"] is True
    assert "access_token" not in response.json() and "recovery_code" not in response.json()
    assert "candidaro_login" not in response.cookies
    denied = client.post("/api/account/login", json={"email": "alex@example.com", "password": PASSWORD})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "EMAIL_VERIFICATION_REQUIRED"
    token = latest_token(factory, "alex@example.com", "verify")
    with factory() as db:
        account = db.query(Account).one()
        assert db.get(AccountSecurity, account.id).terms_version == TERMS_VERSION
        assert db.get(AccountActionToken, token_hash(token)).token_hash != token
        row = db.query(EmailOutbox).one()
        assert token not in row.payload_cipher
        db.add(Login(token_hash=token_hash("synthetic-login"), account_id=account.id, expires_at=account_service.now() + timedelta(days=1)))
        db.commit()
    client.cookies.set("candidaro_login", "synthetic-login")
    assert client.get("/api/account").json()["email"] is None
    assert client.post("/api/account/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/account/verify-email", json={"token": token}).status_code == 400
    assert client.post("/api/account/login", json={"email": "alex@example.com", "password": PASSWORD}).status_code == 200
    assert client.get("/api/account").json()["profile"]["display_name"] == "Alex"


def test_verification_resend_invalidates_old_link_and_expires(lifecycle):
    client, factory = lifecycle
    signup(client)
    old = latest_token(factory, "alex@example.com", "verify")
    unknown = client.post("/api/account/resend-verification", json={"email": "unknown@example.com"})
    result = client.post("/api/account/resend-verification", json={"email": "alex@example.com"})
    assert unknown.json() == result.json()
    new = latest_token(factory, "alex@example.com", "verify")
    assert old != new
    assert client.post("/api/account/verify-email", json={"token": old}).status_code == 400
    with factory() as db:
        db.get(AccountActionToken, token_hash(new)).expires_at = account_service.now() - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/account/verify-email", json={"token": new}).status_code == 400


def test_password_reset_is_generic_expires_single_use_and_revokes_every_session(lifecycle):
    client, factory = lifecycle
    activate(client, factory)
    known = client.post("/api/account/forgot-password", json={"email": "alex@example.com"})
    unknown = client.post("/api/account/forgot-password", json={"email": "unknown@example.com"})
    assert known.json() == unknown.json()
    token = latest_token(factory, "alex@example.com", "reset")
    with factory() as db:
        account = db.query(Account).one()
        db.add(Login(token_hash="second-login", account_id=account.id, expires_at=account_service.now() + timedelta(days=1)))
        db.commit()
    response = client.post("/api/account/reset-password", json={"token": token, "password": NEW_PASSWORD})
    assert response.status_code == 200 and response.json()["sign_in_required"]
    assert client.get("/api/account").json()["email"] is None
    with factory() as db:
        assert db.query(Login).count() == 0
        assert db.query(AccountActionToken).count() == 0
    assert client.post("/api/account/reset-password", json={"token": token, "password": NEW_PASSWORD}).status_code == 400
    assert client.post("/api/account/login", json={"email": "alex@example.com", "password": PASSWORD}).status_code == 401
    assert client.post("/api/account/login", json={"email": "alex@example.com", "password": NEW_PASSWORD}).status_code == 200


def test_profile_changes_and_email_confirmation_do_not_mutate_other_account(lifecycle):
    client, factory = lifecycle
    activate(client, factory)
    response = client.put("/api/account/profile", json={
        "first_name": "Alex", "last_name": "Muster", "language": "sq", "headline": "Hotel manager",
        "preferences": {"email_notifications": True},
    })
    assert response.status_code == 200
    assert response.json()["profile"]["language"] == "sq"
    response = client.post("/api/account/change-email", json={"email": "new@example.com", "current_password": "incorrect", "language": "sq"})
    assert response.status_code == 401
    response = client.post("/api/account/change-email", json={"email": "new@example.com", "current_password": PASSWORD, "language": "sq"})
    assert response.status_code == 200
    assert client.get("/api/account").json()["email"] == "alex@example.com"
    token = latest_token(factory, "new@example.com", "change_email")
    assert client.post("/api/account/verify-email", json={"token": token}).json()["email"] == "new@example.com"
    assert client.get("/api/account").json()["email"] is None
    assert client.post("/api/account/login", json={"email": "new@example.com", "password": PASSWORD}).status_code == 200


def test_password_change_requires_old_password_and_invalidates_pending_links(lifecycle):
    client, factory = lifecycle
    activate(client, factory)
    assert client.post("/api/account/forgot-password", json={"email": "alex@example.com"}).status_code == 200
    token = latest_token(factory, "alex@example.com", "reset")
    assert client.post("/api/account/change-password", json={"current_password": "incorrect", "new_password": NEW_PASSWORD}).status_code == 401
    response = client.post("/api/account/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert response.status_code == 200
    assert client.get("/api/account").json()["email"] is None
    assert client.post("/api/account/reset-password", json={"token": token, "password": PASSWORD}).status_code == 400


def test_guarded_account_deletion_and_export_omit_secrets(lifecycle):
    client, factory = lifecycle
    activate(client, factory)
    with factory() as db:
        account = db.query(Account).one()
        own_session = Session(owner_id=account.id)
        other = Account(email="other@example.com", password_hash="synthetic", recovery_hash="synthetic")
        db.add_all([own_session, other])
        db.flush()
        db.add(Application(session_id=own_session.id, title="My job", status="ready", data_json='{"documents":{"cv":"Own resume"}}'))
        db.commit()
        own_id, other_id = account.id, other.id
    export = client.get("/api/account/export")
    assert export.status_code == 200
    assert export.json()["applications"][0]["data"]["documents"]["cv"] == "Own resume"
    assert "password_hash" not in export.text and "recovery_hash" not in export.text and "payload_cipher" not in export.text
    assert client.request("DELETE", "/api/account", json={"current_password": PASSWORD, "confirmation": "no"}).status_code == 422
    assert client.request("DELETE", "/api/account", json={"current_password": "incorrect", "confirmation": "DELETE"}).status_code == 401
    assert client.request("DELETE", "/api/account", json={"current_password": PASSWORD, "confirmation": "DELETE"}).status_code == 200
    with factory() as db:
        assert db.get(Account, own_id) is None and db.get(Account, other_id) is not None
        assert db.query(Application).count() == 0
        assert db.get(AccountSecurity, own_id) is None
        assert db.get(AccountProfile, own_id) is None
        assert db.query(EmailOutbox).filter_by(account_id=own_id).count() == 0


def test_additive_migration_preserves_admin_existing_users_and_pending_registration(lifecycle):
    _client, factory = lifecycle
    with factory() as db:
        existing = Account(email="existing@example.com", password_hash="old", recovery_hash="old")
        admin = Account(email="info@dafoli.net", password_hash="admin", recovery_hash="admin")
        pending = Account(email="pending@example.com", password_hash="pending", recovery_hash="pending")
        db.add_all([existing, admin, pending])
        db.flush()
        db.add(AdminAccess(account_id=admin.id, enabled=True, secret_cipher="already-encrypted"))
        db.add(AccountSecurity(account_id=pending.id, verification_source="email_pending"))
        db.commit()
        ids = existing.id, admin.id, pending.id
    account_service.migrate_existing_accounts(factory.kw["bind"])
    account_service.migrate_existing_accounts(factory.kw["bind"])
    with factory() as db:
        assert db.get(AccountSecurity, ids[0]).verification_source == "legacy_existing"
        assert db.get(AccountSecurity, ids[0]).verified_at
        assert db.get(AccountSecurity, ids[0]).terms_version is None
        assert db.get(AccountSecurity, ids[1]).verified_at
        assert db.get(AdminAccess, ids[1]).secret_cipher == "already-encrypted"
        assert db.get(AccountSecurity, ids[2]).verified_at is None
        with pytest.raises(HTTPException):
            require_current_terms(db, db.get(Account, ids[0]))


def test_mail_outbox_verified_tls_retries_without_plaintext_tokens(lifecycle, monkeypatch):
    client, factory = lifecycle
    signup(client)
    token = latest_token(factory, "alex@example.com", "verify")
    seen = []

    def fail(_message):
        raise smtplib.SMTPException("private SMTP response must not be logged")

    monkeypatch.setattr(account_mail, "send_message", fail)
    assert account_mail.drain(session_factory=factory)["failed"] == 1
    with factory() as db:
        row = db.query(EmailOutbox).one()
        assert row.status == "pending" and row.attempts == 1 and token not in row.payload_cipher
        row.next_attempt_at = account_service.now() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(account_mail, "send_message", lambda message: seen.append(message))
    assert account_mail.drain(session_factory=factory)["sent"] == 1
    assert "#verify-email=" + token in seen[0].get_body(preferencelist=("plain",)).get_content()
    assert "?token=" not in seen[0].get_body(preferencelist=("plain",)).get_content()
    with factory() as db:
        row = db.query(EmailOutbox).one()
        assert row.status == "sent" and row.payload_cipher is None
    assert account_mail.drain(session_factory=factory)["sent"] == 0


def test_smtp_starttls_is_required_before_credentials(lifecycle, monkeypatch):
    _client, _factory = lifecycle
    calls = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            assert kwargs["timeout"] == 15
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def ehlo(self):
            calls.append("ehlo")
        def starttls(self, context):
            assert context.check_hostname
            calls.append("tls")
        def login(self, *args):
            calls.append("login")
        def send_message(self, *args):
            calls.append("send")

    monkeypatch.setattr(account_mail.smtplib, "SMTP", SMTP)
    account_mail.send_message(None)
    assert calls == ["ehlo", "tls", "ehlo", "login", "send"]


def test_recovery_codes_are_disabled(lifecycle):
    client, _factory = lifecycle
    response = client.post("/api/account/recover", json={"email": "alex@example.com", "recovery_code": "obsolete", "password": NEW_PASSWORD})
    assert response.status_code == 410


def test_https_relay_hmac_has_exact_raw_body_and_no_redirects(lifecycle, monkeypatch):
    import hashlib
    import hmac
    from types import SimpleNamespace

    client, factory = lifecycle
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_enabled", False)
    monkeypatch.setattr(settings, "mail_transport", "https_relay")
    monkeypatch.setattr(settings, "mail_relay_url", "https://tafolli.net/.well-known/tafolliboost-mail.php")
    monkeypatch.setattr(settings, "mail_relay_secret", "synthetic-relay-secret-" + "z" * 40)
    assert account_mail.ready()
    assert signup(client).status_code == 200
    seen = []

    def relay(url, **kwargs):
        assert url == settings.mail_relay_url and kwargs["follow_redirects"] is False
        assert kwargs["timeout"] == 15
        headers = kwargs["headers"]
        expected = hmac.new(settings.mail_relay_secret.encode(), (
            headers["X-Tafolli-Timestamp"].encode() + b"\n" + headers["X-Tafolli-Nonce"].encode()
            + b"\n" + kwargs["content"]
        ), hashlib.sha256).hexdigest()
        assert headers["X-Tafolli-Signature"] == expected
        payload = json.loads(kwargs["content"])
        assert payload["recipient"] == "alex@example.com"
        assert "#verify-email=" in payload["text"]
        assert 'href="https://tafolliboost.com/' in payload["html"]
        assert settings.mail_relay_secret not in kwargs["content"].decode()
        seen.append(payload)
        return SimpleNamespace(status_code=200, json=lambda: {"accepted": True})

    monkeypatch.setattr(account_mail.httpx, "post", relay)
    assert account_mail.drain(session_factory=factory)["sent"] == 1
    assert len(seen) == 1
    monkeypatch.setattr(settings, "mail_relay_url", "https://user:secret@tafolli.net/mail")
    assert not account_mail.ready()


def test_replayed_or_expired_reset_link_cannot_verify_email(lifecycle):
    client, factory = lifecycle
    activate(client, factory)
    assert client.post("/api/account/forgot-password", json={"email": "alex@example.com"}).status_code == 200
    token = latest_token(factory, "alex@example.com", "reset")
    assert client.post("/api/account/verify-email", json={"token": token}).status_code == 400
    with factory() as db:
        row = db.get(AccountActionToken, token_hash(token))
        row.expires_at = account_service.now() - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/account/reset-password", json={"token": token, "password": NEW_PASSWORD}).status_code == 400


def test_verified_account_gets_durable_terms_and_withdrawal_copy(lifecycle):
    from backend.services.legal_service import render_text

    client, factory = lifecycle
    activate(client, factory)
    with factory() as db:
        receipt = db.query(EmailOutbox).filter_by(purpose="receipt").one()
        payload = json.loads(account_mail.cipher().decrypt(receipt.payload_cipher.encode()))
        assert render_text("terms", "de") in payload["text"]
        assert render_text("withdrawal", "de") in payload["text"]
        assert TERMS_VERSION in payload["text"]
        account = db.query(Account).one()
        accepted_at = db.get(AccountSecurity, account.id).terms_accepted_at
    consent = {"terms_accepted": True, "privacy_acknowledged": True, "terms_version": TERMS_VERSION}
    assert client.post("/api/account/accept-terms", json=consent).status_code == 200
    with factory() as db:
        assert db.query(EmailOutbox).filter_by(purpose="receipt").count() == 1
        assert db.get(AccountSecurity, account.id).terms_accepted_at == accepted_at


def test_https_relay_dns_pin_preserves_host_sni_and_certificate_validation(lifecycle, monkeypatch):
    from types import SimpleNamespace

    client, factory = lifecycle
    settings = get_settings()
    monkeypatch.setattr(settings, "mail_transport", "https_relay")
    monkeypatch.setattr(settings, "mail_relay_url", "https://tafolli.net/.well-known/tafolliboost-mail.php")
    monkeypatch.setattr(settings, "mail_relay_secret", "synthetic-relay-secret-" + "p" * 40)
    monkeypatch.setattr(settings, "mail_relay_connect_ip", "66.33.213.184")
    assert signup(client).status_code == 200
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 15, "follow_redirects": False, "trust_env": False}
            # No verify=False override; HTTPX verifies the certificate by default.
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def build_request(self, method, url, **kwargs):
            assert method == "POST"
            assert str(url) == "https://66.33.213.184/.well-known/tafolliboost-mail.php"
            assert kwargs["headers"]["Host"] == "tafolli.net"
            assert kwargs["extensions"] == {"sni_hostname": "tafolli.net"}
            calls.append(kwargs)
            return object()
        def send(self, request):
            return SimpleNamespace(status_code=200, json=lambda: {"accepted": True})

    monkeypatch.setattr(account_mail.httpx, "Client", Client)
    assert account_mail.drain(session_factory=factory)["sent"] == 1
    assert len(calls) == 1
    monkeypatch.setattr(settings, "mail_relay_connect_ip", "127.0.0.1")
    assert not account_mail.ready()


def test_registration_address_cannot_inject_additional_mail_recipients(lifecycle):
    client, factory = lifecycle
    for email in ("a,b@example.com", "Name <alex@example.com>", "alex@example.com\nBcc:other@example.com", "alex..name@example.com"):
        assert signup(client, email=email).status_code == 422
    with factory() as db:
        assert db.query(Account).count() == 0 and db.query(EmailOutbox).count() == 0


@pytest.mark.parametrize("operation", ["reset", "password_change", "email_change"])
def test_credential_rotation_preserves_pending_and_leased_contract_receipts(lifecycle, operation):
    client, factory = lifecycle
    activate(client, factory)
    with factory() as db:
        account = db.query(Account).one()
        pending = account_mail.queue_receipt(db, account, "Purchase confirmation", "Purchased credits and accepted contractual information.")
        sending = account_mail.queue_receipt(db, account, "Withdrawal received", "A durable receipt of the customer's withdrawal.")
        sending.status = "sending"
        sending.attempts = 1
        sending.lease_until = account_service.now() + timedelta(minutes=2)
        db.commit()
        receipts = {
            row.id: (row.status, row.payload_cipher, row.lease_until, row.recipient)
            for row in db.query(EmailOutbox).filter_by(purpose="receipt").all()
        }
        assert pending.id in receipts and sending.id in receipts
    assert client.post("/api/account/forgot-password", json={"email": "alex@example.com"}).status_code == 200
    reset_token = latest_token(factory, "alex@example.com", "reset")
    if operation == "reset":
        response = client.post("/api/account/reset-password", json={"token": reset_token, "password": NEW_PASSWORD})
    elif operation == "password_change":
        response = client.post("/api/account/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    else:
        assert client.post("/api/account/change-email", json={"email": "new@example.com", "current_password": PASSWORD}).status_code == 200
        verification_token = latest_token(factory, "new@example.com", "change_email")
        response = client.post("/api/account/verify-email", json={"token": verification_token})
    assert response.status_code == 200, response.text
    assert client.get("/api/account").json()["email"] is None
    with factory() as db:
        assert db.query(AccountActionToken).count() == 0
        for receipt_id, original in receipts.items():
            row = db.get(EmailOutbox, receipt_id)
            assert (row.status, row.payload_cipher, row.lease_until, row.recipient) == original
        obsolete = db.query(EmailOutbox).filter_by(purpose="reset").one()
        assert obsolete.status == "failed" and obsolete.payload_cipher is None
