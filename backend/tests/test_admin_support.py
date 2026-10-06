"""Support edits are versioned, allowlisted, audited and never change credentials."""

import json
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend import schemas
from backend.account_models import AccountActionToken, AccountProfile, AccountSecurity, EmailOutbox
from backend.account_terms import TERMS_VERSION
from backend.config import get_settings
from backend.database import Base, get_db
from backend.main import app
from backend.models import Account, AdminAccess, AdminAudit, AdminLogin, Login
from backend.profile_schema import AdminPasswordResetRequest, AdminProfilePatch
from backend.services import account_mail
from backend.services import account_service as accounts
from backend.services import admin_support as support
from backend.services.session_service import token_hash


@pytest.fixture
def support_db(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "support.db"), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    settings = get_settings()
    for key, value in {
        "hosted_ai_enabled": False, "site_url": "https://tafolliboost.com", "smtp_enabled": True,
        "smtp_host": "smtp.example.invalid", "smtp_username": "operator@example.invalid",
        "smtp_password": "synthetic-password", "mail_transport": "smtp", "mail_key_file": str(tmp_path / "mail.key"),
    }.items():
        monkeypatch.setattr(settings, key, value)
    with factory() as db:
        admin = Account(email="operator@example.com", password_hash="admin-password", recovery_hash="admin-recovery")
        user = Account(email="user@example.com", password_hash="unchanged-password", recovery_hash="unchanged-recovery")
        reserved = Account(email="info@tafolli.net", password_hash="reserved-password", recovery_hash="reserved-recovery")
        db.add_all([admin, user, reserved])
        db.flush()
        db.add_all([
            AdminAccess(account_id=admin.id, enabled=True, secret_cipher="mfa-unchanged", last_counter=18),
            AccountSecurity(account_id=user.id, verified_at=accounts.now(), credential_version=7),
            AccountProfile(account_id=user.id, first_name="Before", country="DE", spoken_languages='["Deutsch"]'),
            Login(token_hash=token_hash("normal-login"), account_id=user.id, expires_at=accounts.now() + timedelta(days=1)),
            AdminLogin(token_hash=token_hash("admin-login"), account_id=admin.id, expires_at=accounts.now() + timedelta(minutes=10)),
        ])
        db.commit()
        ids = admin.id, user.id, reserved.id

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app, headers={"X-Boosty-Request": "1"}), factory, ids
    app.dependency_overrides.clear()
    engine.dispose()


def patch(profile, expected):
    return AdminProfilePatch(profile=profile, expected_updated_at=expected, reason="Requested spelling correction")


def test_edit_commits_profile_and_safe_audit_without_affecting_security(support_db):
    _client, factory, (admin_id, user_id, _reserved) = support_db
    with factory() as db:
        before = support.user_details(db, db.get(Account, user_id))
        result = support.update_profile(db, db.get(Account, admin_id), user_id, patch({
            "first_name": " Alex ", "gender": "diverse", "date_of_birth": "1992-02-29",
            "street": "Main street 12", "postal_code": "10115", "city": "Berlin", "country": " de ",
            "spoken_languages": [" Deutsch ", "English"], "preferences": {"email_notifications": True},
        }, before["profile_updated_at"]))
        assert result["profile"]["first_name"] == "Alex"
        assert result["profile"]["date_of_birth"] == "1992-02-29"
        assert result["profile"]["country"] == "DE"
        assert result["profile"]["spoken_languages"] == ["Deutsch", "English"]
        assert result["profile_updated_at"] != before["profile_updated_at"]
        account = db.get(Account, user_id)
        assert (account.password_hash, account.recovery_hash) == ("unchanged-password", "unchanged-recovery")
        assert db.get(AccountSecurity, user_id).credential_version == 7
        assert db.query(Login).count() == 1
        assert db.get(AdminAccess, admin_id).secret_cipher == "mfa-unchanged"
        assert db.get(AdminAccess, admin_id).last_counter == 18
        audit = db.query(AdminAudit).one()
        assert (audit.admin_id, audit.subject_id, audit.action) == (admin_id, user_id, "user.profile.updated")
        assert audit.reason == "Requested spelling correction"
        assert json.loads(audit.changed_fields_json) == [
            "city", "country", "date_of_birth", "first_name", "gender", "postal_code",
            "preferences.email_notifications", "spoken_languages", "street",
        ]
        assert "Alex" not in audit.changed_fields_json


def test_stale_edit_returns_conflict_preserves_data_and_does_not_audit_success(support_db):
    _client, factory, (admin_id, user_id, _reserved) = support_db
    with factory() as db:
        stale = support.user_details(db, db.get(Account, user_id))["profile_updated_at"]
    with factory() as db:
        profile = db.get(AccountProfile, user_id)
        profile.first_name, profile.updated_at = "Newer user edit", profile.updated_at + timedelta(microseconds=1)
        db.commit()
    with factory() as db:
        with pytest.raises(HTTPException) as error:
            support.update_profile(db, db.get(Account, admin_id), user_id, patch({"first_name": "Old form"}, stale))
        assert error.value.status_code == 409
        assert error.value.detail["code"] == "PROFILE_CONFLICT"
        assert db.get(AccountProfile, user_id).first_name == "Newer user edit"
        assert db.query(AdminAudit).count() == 0


@pytest.mark.parametrize("profile", [
    {"role": "admin"}, {"password_hash": "new"}, {"credits": 100}, {"verified_at": "2026-01-01"},
    {"date_of_birth": "2025-02-29"}, {"date_of_birth": "2000-01-01T00:00:00Z"},
    {"date_of_birth": (date.today() + timedelta(days=1)).isoformat()}, {"country": "XX"}, {"country": []},
    {"spoken_languages": ["English"] * 21}, {"spoken_languages": ["x" * 41]}, {"spoken_languages": [" "]},
])
def test_shared_validation_rejects_privileged_and_invalid_profile_fields(profile):
    with pytest.raises(ValidationError):
        schemas.AccountProfileUpdate.model_validate(profile)
    with pytest.raises(ValidationError):
        patch(profile, None)
    registration = {"email": "new@example.com", "password": "password-not-trimmed", "terms_accepted": True,
                    "privacy_acknowledged": True, "terms_version": TERMS_VERSION, **profile}
    with pytest.raises(ValidationError):
        schemas.AccountRegistration.model_validate(registration)


@pytest.mark.parametrize("reason", ["no", "    ", "x" * 501])
def test_both_support_actions_require_substantive_bounded_reason(reason):
    with pytest.raises(ValidationError):
        AdminProfilePatch(profile={"first_name": "Alex"}, expected_updated_at=None, reason=reason)
    with pytest.raises(ValidationError):
        AdminPasswordResetRequest(reason=reason)


def test_support_rejects_regular_actor_admin_and_reserved_targets(support_db):
    _client, factory, (admin_id, user_id, reserved_id) = support_db
    for actor, target in [(user_id, user_id), (admin_id, admin_id), (admin_id, reserved_id)]:
        with factory() as db:
            for action in (
                lambda actor=actor, target=target: support.update_profile(db, db.get(Account, actor), target, patch({"first_name": "Changed"}, None)),
                lambda actor=actor, target=target: support.request_password_reset(db, db.get(Account, actor), target, AdminPasswordResetRequest(reason="User requested password help")),
            ):
                with pytest.raises(HTTPException) as error:
                    action()
                assert error.value.status_code == 403
            assert db.query(AdminAudit).count() == 0
            assert db.query(EmailOutbox).count() == 0
    with factory() as db:
        assert support.user_details(db, db.get(Account, admin_id))["profile_editable"] is False
        assert support.user_details(db, db.get(Account, reserved_id))["password_reset_allowed"] is False


def test_reset_queues_existing_single_use_flow_no_credential_changes_or_token_response(support_db):
    client, factory, (admin_id, user_id, _reserved) = support_db
    with factory() as db:
        result = support.request_password_reset(db, db.get(Account, admin_id), user_id,
            AdminPasswordResetRequest(reason="User requested password help"))
        assert result == {"ok": True, "status": "reset_email_queued"}
        assert "token" not in json.dumps(result)
        assert db.get(Account, user_id).password_hash == "unchanged-password"
        assert db.get(AccountSecurity, user_id).credential_version == 7
        assert db.query(Login).count() == 1
        action = db.query(AccountActionToken).one()
        assert action.purpose == "reset" and timedelta(minutes=29) < action.expires_at - accounts.now() <= timedelta(minutes=30)
        outbox = db.query(EmailOutbox).one()
        assert outbox.recipient == "user@example.com" and outbox.purpose == "reset"
        token = json.loads(account_mail.cipher().decrypt(outbox.payload_cipher.encode()))["token"]
        audit = db.query(AdminAudit).one()
        assert audit.action == "user.password_reset.requested" and json.loads(audit.changed_fields_json) == []
        assert token not in audit.reason and token not in audit.changed_fields_json
    response = client.post("/api/account/reset-password", json={"token": token, "password": "new-private-password-123"})
    assert response.status_code == 200
    assert client.post("/api/account/reset-password", json={"token": token, "password": "new-private-password-123"}).status_code == 400
    with factory() as db:
        assert db.query(Login).count() == 0
        assert accounts.password_matches("new-private-password-123", db.get(Account, user_id).password_hash)


def test_pending_reset_and_mail_failure_leave_no_token_or_success_audit(support_db, monkeypatch):
    _client, factory, (admin_id, user_id, _reserved) = support_db
    with factory() as db:
        db.get(AccountSecurity, user_id).verified_at = None
        db.commit()
        with pytest.raises(HTTPException) as error:
            support.request_password_reset(db, db.get(Account, admin_id), user_id, AdminPasswordResetRequest(reason="Requested account assistance"))
        assert error.value.status_code == 409
        db.get(AccountSecurity, user_id).verified_at = accounts.now()
        db.commit()
        monkeypatch.setattr(get_settings(), "smtp_enabled", False)
        with pytest.raises(HTTPException) as error:
            support.request_password_reset(db, db.get(Account, admin_id), user_id, AdminPasswordResetRequest(reason="Requested account assistance"))
        assert error.value.status_code == 503
        assert db.query(AdminAudit).count() == db.query(EmailOutbox).count() == db.query(AccountActionToken).count() == 0


def test_registration_profile_and_export_roundtrip_preserve_omitted_fields(support_db):
    client, factory, (_admin, _user, _reserved) = support_db
    password = "  password-with-intentional-spaces  "
    response = client.post("/api/account/register", json={
        "email": "new@example.com", "password": password, "terms_accepted": True,
        "privacy_acknowledged": True, "terms_version": TERMS_VERSION,
        "first_name": " New ", "last_name": "User", "date_of_birth": "1990-12-31", "gender": "female",
        "street": "Example street", "postal_code": "12345", "city": "Hamburg", "country": "de",
        "spoken_languages": ["Deutsch", "English"],
    })
    assert response.status_code == 200
    with factory() as db:
        account = db.query(Account).filter_by(email="new@example.com").one()
        assert accounts.password_matches(password, account.password_hash)
        db.get(AccountSecurity, account.id).verified_at = accounts.now()
        db.commit()
    assert client.post("/api/account/login", json={"email": "new@example.com", "password": password}).status_code == 200
    result = client.put("/api/account/profile", json={"headline": "A new headline"})
    assert result.status_code == 200
    assert result.json()["profile"]["first_name"] == "New"
    assert result.json()["profile"]["spoken_languages"] == ["Deutsch", "English"]
    exported = client.get("/api/account/export")
    assert exported.status_code == 200 and exported.json()["account"]["profile"]["date_of_birth"] == "1990-12-31"
    assert all(secret not in exported.text for secret in ("password_hash", "recovery_hash", "payload_cipher"))


def test_support_routes_require_admin_session_validate_allowlist_and_reject_stale_draft(support_db):
    client, factory, (admin_id, user_id, reserved_id) = support_db
    with factory() as db:
        expected = support.user_details(db, db.get(Account, user_id))["profile_updated_at"]
    body = {"profile": {"first_name": "Route edit"}, "expected_updated_at": expected, "reason": "User requested spelling correction"}
    url = f"/api/admin/users/{user_id}/profile"
    assert client.patch(url, json=body).status_code == 401
    assert client.patch(url, json=body, headers={"Authorization": "Bearer normal-login"}).status_code == 401
    headers = {"Authorization": "Bearer admin-login"}
    assert client.patch(url, json={**body, "profile": {"role": "admin"}}, headers=headers).status_code == 422
    response = client.patch(url, json=body, headers=headers)
    assert response.status_code == 200 and response.json()["profile"]["first_name"] == "Route edit"
    assert client.patch(url, json=body, headers=headers).status_code == 409
    for target in (admin_id, reserved_id):
        assert client.patch(f"/api/admin/users/{target}/profile", json=body, headers=headers).status_code == 403
    with factory() as db:
        assert db.query(AdminAudit).filter_by(action="user.profile.updated").count() == 1
        assert db.get(Account, user_id).password_hash == "unchanged-password"


def test_reset_route_requires_admin_session_and_never_accepts_a_direct_password(support_db):
    client, factory, (admin_id, user_id, reserved_id) = support_db
    headers = {"Authorization": "Bearer admin-login"}
    reset_url = f"/api/admin/users/{user_id}/password-reset"
    reset_body = {"reason": "User requested password assistance"}
    assert client.post(reset_url, json=reset_body).status_code == 401
    assert client.post(reset_url, json={**reset_body, "password": "direct-change-prohibited"}, headers=headers).status_code == 422
    response = client.post(reset_url, json=reset_body, headers=headers)
    assert response.status_code == 200 and response.json() == {"ok": True, "status": "reset_email_queued"}
    for target in (admin_id, reserved_id):
        assert client.post(f"/api/admin/users/{target}/password-reset", json=reset_body, headers=headers).status_code == 403
    with factory() as db:
        assert db.query(AdminAudit).filter_by(action="user.password_reset.requested").count() == 1
        assert db.get(Account, user_id).password_hash == "unchanged-password"
