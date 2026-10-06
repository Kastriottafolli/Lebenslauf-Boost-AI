"""Administrative authorization, MFA, protected data access and retention boundaries."""

import json
import re
import secrets
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.account_models import AccountActionToken, AccountProfile, AccountSecurity, EmailOutbox
from backend.config import get_settings
from backend.database import Base, get_db
from backend.main import app
from backend.models import (
    Account,
    Activity,
    AdminAccess,
    AdminAudit,
    AdminLogin,
    Application,
    AuthAttempt,
    DailyMetric,
    Login,
    Session,
)
from backend.services import admin_service as admins
from backend.services.account_service import password_hash
from backend.services.session_service import token_hash

PASSWORD = "synthetic-admin-password-1234"


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/admin-test.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(get_settings(), "admin_key_file", str(tmp_path / "encryption.key"))
    monkeypatch.setattr(get_settings(), "secure_cookies", True)
    monkeypatch.setattr(get_settings(), "admin_require_totp", True)
    clock = [1800000000]
    monkeypatch.setattr(admins.time, "time", lambda: clock[0])

    def dependency():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    client = TestClient(app, base_url="https://testserver", headers={"X-Boosty-Request": "1"})
    with factory() as db:
        path = admins.provision(db, "admin@example.com", tmp_path / "private")
    text = path.read_text()
    setup = {
        "email": "admin@example.com",
        "setup_code": re.search(r"Einrichtungscode: (\S+)", text)[1],
    }
    yield client, factory, setup, clock, path
    app.dependency_overrides.clear()
    engine.dispose()


def complete(env):
    client, _factory, setup, clock, _path = env
    result = client.post("/api/admin/setup/begin", json=setup)
    assert result.status_code == 200, result.text
    secret = result.json()["secret"]
    result = client.post(
        "/api/admin/setup/finish",
        json={**setup, "password": PASSWORD, "code": admins.totp(secret, clock[0] // 30)},
    )
    assert result.status_code == 200, result.text
    return secret, result


def test_rfc6238_totp_vector():
    # RFC 6238 SHA-1 test vector: 59 seconds -> 94287082 (last six digits).
    assert admins.totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 1) == "287082"


@pytest.mark.parametrize("requires_totp", [True, False])
def test_authentication_mode_only_discloses_server_policy(env, monkeypatch, requires_totp):
    client, _factory, _setup, _clock, _path = env
    monkeypatch.setattr(get_settings(), "admin_require_totp", requires_totp)
    response = client.get("/api/admin/auth-options")
    assert response.status_code == 200
    assert response.json() == {"requires_totp": requires_totp}
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/admin/auth-options", headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert TestClient(app).get("/api/admin/auth-options").status_code == 403


def test_password_only_login_preserves_credentials_and_mfa_state(env, monkeypatch):
    client, factory, setup, _clock, _path = env
    complete(env)
    assert client.post("/api/admin/logout", json={}).status_code == 200
    with factory() as db:
        account = db.query(Account).one()
        access = db.query(AdminAccess).one()
        original = (account.id, account.password_hash, access.secret_cipher, access.last_counter)
    monkeypatch.setattr(get_settings(), "admin_require_totp", False)
    credentials = {"email": setup["email"], "password": PASSWORD}
    assert client.post("/api/admin/login", json={**credentials, "password": "wrong-password-1234"}).status_code == 401
    result = client.post("/api/admin/login", json=credentials)
    assert result.status_code == 200
    assert result.json()["email"] == setup["email"]
    assert "HttpOnly" in result.headers["set-cookie"]
    assert "SameSite=strict" in result.headers["set-cookie"]
    assert client.get("/api/admin/overview").status_code == 200
    with factory() as db:
        account, access = db.query(Account).one(), db.query(AdminAccess).one()
        assert (account.id, account.password_hash, access.secret_cipher, access.last_counter) == original
    assert client.post("/api/admin/logout", json={}).status_code == 200
    assert client.get("/api/admin/me").status_code == 401
    # Re-enabling MFA still requires a valid code; client fields cannot bypass it.
    monkeypatch.setattr(get_settings(), "admin_require_totp", True)
    assert client.post("/api/admin/login", json=credentials).status_code == 401
    assert client.post("/api/admin/login", json={**credentials, "requires_totp": False}).status_code == 422


def test_password_only_private_setup_requires_private_code_and_is_single_use(env, monkeypatch):
    client, factory, setup, _clock, _path = env
    monkeypatch.setattr(get_settings(), "admin_require_totp", False)
    assert client.post("/api/admin/setup/begin", json={**setup, "setup_code": secrets.token_urlsafe(32)}).status_code == 401
    result = client.post("/api/admin/setup/begin", json=setup)
    assert result.json() == {"requires_totp": False}
    credentials = {**setup, "password": PASSWORD}
    assert client.post("/api/admin/setup/finish", json={**credentials, "password": "too-short"}).status_code == 422
    assert client.post("/api/admin/setup/finish", json=credentials).status_code == 200
    assert client.post("/api/admin/setup/finish", json=credentials).status_code == 401
    with factory() as db:
        access = db.query(AdminAccess).one()
        assert access.enabled and access.setup_hash is None and access.last_counter == -1
        assert access.secret_cipher
    assert client.get("/api/admin/me").status_code == 200


def test_password_only_login_still_rejects_non_admin_disabled_and_unknown_accounts(env, monkeypatch):
    client, factory, setup, _clock, _path = env
    monkeypatch.setattr(get_settings(), "admin_require_totp", False)
    with factory() as db:
        db.add(Account(email="ordinary@example.com", password_hash=password_hash(PASSWORD), recovery_hash=token_hash("synthetic-recovery")))
        # A provisioned but inactive admin must not sign in even with a matching password.
        db.query(Account).filter_by(email=setup["email"]).one().password_hash = password_hash(PASSWORD)
        db.commit()
    for email in ("ordinary@example.com", "missing@example.com", setup["email"]):
        assert client.post("/api/admin/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert client.get("/api/admin/users").status_code == 401


@pytest.mark.parametrize("requires_totp", [True, False])
def test_identity_limits_apply_to_both_admin_authentication_modes(env, monkeypatch, requires_totp):
    client, factory, setup, _clock, _path = env
    complete(env)
    monkeypatch.setattr(get_settings(), "admin_require_totp", requires_totp)
    with factory() as db:
        from backend.services.account_service import limit_identity

        for _ in range(10):
            limit_identity(db, setup["email"], "admin")
    assert client.post("/api/admin/login", json={"email": setup["email"], "password": PASSWORD}).status_code == 429


def test_admin_never_granted_by_public_registration_or_email(env, monkeypatch):
    from backend.account_models import EmailOutbox
    from backend.account_terms import TERMS_VERSION
    from backend.services import account_mail

    client, factory, setup, _clock, _path = env
    monkeypatch.setattr(account_mail, "ready", lambda: True)
    monkeypatch.setattr(get_settings(), "mail_key_file", str(_path.parent / "mail.key"))
    consent = {"terms_accepted": True, "privacy_acknowledged": True, "terms_version": TERMS_VERSION}
    existing = client.post("/api/account/register", json={"email": setup["email"], "password": PASSWORD, **consent})
    assert existing.status_code == 200 and "access_token" not in existing.json()
    assert client.post("/api/account/register", json={
        "email": "normal@example.com", "password": PASSWORD, **consent,
        "is_admin": True, "role": "admin",
    }).status_code == 422
    normal = client.post("/api/account/register", json={
        "email": "normal@example.com", "password": PASSWORD, **consent,
    })
    assert normal.status_code == 200
    with factory() as db:
        mail = db.query(EmailOutbox).filter_by(recipient="normal@example.com").one()
        token = json.loads(account_mail.cipher().decrypt(mail.payload_cipher.encode()))["token"]
    assert client.post("/api/account/verify-email", json={"token": token}).status_code == 200
    login = client.post("/api/account/login", json={"email": "normal@example.com", "password": PASSWORD})
    assert login.status_code == 200
    for route in ("overview", "users", "events", "audit", "database", "sessions"):
        assert client.get("/api/admin/" + route).status_code == 401
    client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    assert client.get("/api/admin/users").status_code == 401
    with factory() as db:
        assert db.query(AdminAccess).count() == 1
        assert not db.query(AdminAccess).one().enabled
        with pytest.raises(ValueError):
            admins.provision(db, "normal@example.com", _path.parent)


def test_private_provisioning_and_one_time_setup(env):
    client, factory, setup, _clock, path = env
    assert path.stat().st_mode & 0o777 == 0o600
    assert (
        client.post(
            "/api/admin/setup/begin", json={**setup, "setup_code": secrets.token_urlsafe(32)}
        ).status_code
        == 401
    )
    secret, result = complete(env)
    cookie = result.headers["set-cookie"]
    assert (
        "HttpOnly" in cookie
        and "Secure" in cookie
        and "SameSite=strict" in cookie
        and "Max-Age=900" in cookie
    )
    assert client.post("/api/admin/setup/begin", json=setup).status_code == 401
    with factory() as db:
        access = db.query(AdminAccess).one()
        assert access.enabled and access.setup_hash is None
        assert secret not in access.secret_cipher
        assert admins.cipher().decrypt(access.secret_cipher.encode()).decode() == secret
        account = db.query(Account).one()
        assert PASSWORD not in account.password_hash
        assert result.json()["access_token"] not in db.query(AdminLogin).one().token_hash
    assert client.get("/api/admin/overview").status_code == 200
    assert (
        client.post(
            "/api/account/login", json={"email": setup["email"], "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/account/recover",
            json={
                "email": setup["email"],
                "password": PASSWORD,
                "recovery_code": setup["setup_code"],
            },
        ).status_code
        == 410
    )


def test_setup_expiry_and_invalid_otp(env):
    client, factory, setup, _clock, _path = env
    assert (
        client.post(
            "/api/admin/setup/finish", json={**setup, "password": PASSWORD, "code": "000000"}
        ).status_code
        == 401
    )
    with factory() as db:
        access = db.query(AdminAccess).one()
        access.setup_expires_at = admins.now() - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/admin/setup/begin", json=setup).status_code == 401


def test_mfa_replay_logout_and_expiry(env):
    client, factory, setup, clock, _path = env
    secret, _result = complete(env)
    credentials = {
        "email": setup["email"],
        "password": PASSWORD,
        "code": admins.totp(secret, clock[0] // 30),
    }
    assert client.post("/api/admin/login", json=credentials).status_code == 401
    assert client.post("/api/admin/logout", json={}).status_code == 200
    assert client.get("/api/admin/overview").status_code == 401
    clock[0] += 30
    credentials["code"] = admins.totp(secret, clock[0] // 30)
    assert (
        client.post(
            "/api/admin/login", json={**credentials, "password": "wrong-password-1234"}
        ).status_code
        == 401
    )
    assert client.post("/api/admin/login", json=credentials).status_code == 200
    assert client.post("/api/admin/login", json=credentials).status_code == 401
    with factory() as db:
        row = db.query(AdminLogin).one()
        row.expires_at = admins.now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/admin/overview").status_code == 401


def test_admin_csrf_and_origin_restrictions(env):
    client, _factory, setup, _clock, _path = env
    assert TestClient(app).post("/api/admin/setup/begin", json=setup).status_code == 403
    assert (
        client.post(
            "/api/admin/setup/begin", json=setup, headers={"Origin": "https://evil.invalid"}
        ).status_code
        == 403
    )
    complete(env)
    assert (
        client.get("/api/admin/users", headers={"Origin": "https://evil.invalid"}).status_code
        == 403
    )
    assert client.get("/api/admin/users?limit=1000").status_code == 422
    page = client.get("/admin")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "noindex" in page.headers["x-robots-tag"]
    assert "max-age=" in page.headers["strict-transport-security"]


def test_audited_data_views_exclude_secrets_and_handle_search(env):
    client, factory, _setup, _clock, _path = env
    complete(env)
    with factory() as db:
        account = Account(
            email="person@example.com",
            password_hash=password_hash(PASSWORD),
            recovery_hash=token_hash("do-not-expose"),
        )
        db.add(account)
        db.flush()
        sess = Session(owner_id=account.id, owner_token_hash=token_hash("private-session-token"))
        db.add(sess)
        db.flush()
        project = Application(
            session_id=sess.id,
            title="Support example",
            data_json=json.dumps(
                {"profile": {"name": "Synthetic Person"}, "documents": {"cv": "Synthetic CV"}}
            ),
        )
        db.add(project)
        db.flush()
        account_id, project_id = account.id, project.id
        db.add(Activity(account_id=account.id, event="project.save", outcome=200))
        db.add(DailyMetric(day=admins.now().date().isoformat(), page_views=12, visits=4))
        db.commit()
    users = client.get("/api/admin/users").json()
    assert users["total"] == 2
    assert client.get("/api/admin/users?q=%25").json()["total"] == 0
    assert client.get("/api/admin/users?q=person").json()["total"] == 1
    assert (
        client.get("/api/admin/users/" + account_id).json()["applications"][0]["id"] == project_id
    )
    assert (
        client.get("/api/admin/applications/" + project_id).json()["data"]["profile"]["name"]
        == "Synthetic Person"
    )
    overview = client.get("/api/admin/overview").json()
    assert overview["totals"]["page_views"] == 12 and overview["totals"]["active_accounts"] == 1
    for route in ("users", "events", "database", "sessions", "audit"):
        response = client.get("/api/admin/" + route)
        assert response.status_code == 200, response.text
        assert "password_hash" not in response.text and "recovery_hash" not in response.text
        assert "do-not-expose" not in response.text and "private-session-token" not in response.text
    with factory() as db:
        assert (
            db.query(AdminAudit)
            .filter_by(action="application.content.read", subject_id=project_id)
            .count()
            == 1
        )


def test_persistent_identity_rate_limit_and_revocation(env):
    client, factory, setup, clock, _path = env
    secret, _result = complete(env)
    for _ in range(9):
        with factory() as db:
            from backend.services.account_service import limit_identity

            limit_identity(db, setup["email"], "admin")
    clock[0] += 30
    credentials = {
        "email": setup["email"],
        "password": PASSWORD,
        "code": admins.totp(secret, clock[0] // 30),
    }
    assert client.post("/api/admin/login", json=credentials).status_code == 200
    assert client.post("/api/admin/login", json=credentials).status_code == 429
    with factory() as db:
        assert (
            db.query(AuthAttempt).filter_by(bucket=token_hash("admin:" + setup["email"])).count()
            == 10
        )
        access = db.query(AdminAccess).one()
        access.enabled = False
        db.commit()
    assert client.get("/api/admin/overview").status_code == 403


def test_native_preflight_and_sibling_origins_are_separated(env):
    client, _factory, _setup, _clock, _path = env
    response = client.options(
        "/api/admin/login",
        headers={
            "Origin": "capacitor://localhost",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-boosty-request",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "capacitor://localhost"
    assert (
        client.get("/api/admin/users", headers={"Origin": "https://www.tafolli.net"}).status_code
        == 403
    )


def test_admin_recovery_only_from_server_revokes_sessions(env):
    client, factory, setup, _clock, path = env
    complete(env)
    with factory() as db:
        replacement = admins.provision(db, setup["email"], path.parent, reset_existing=True)
        assert db.query(AdminLogin).count() == 0
        assert not db.query(AdminAccess).one().enabled
        assert db.query(AdminAudit).filter_by(action="admin.cli.reset").count() == 1
    assert replacement != path
    assert client.get("/api/admin/users").status_code == 401
    assert client.post("/api/admin/setup/begin", json=setup).status_code == 401


def test_server_admin_email_correction_preserves_credentials_mfa_and_owned_data(env):
    client, factory, setup, clock, _path = env
    secret, _result = complete(env)
    with factory() as db:
        account = db.query(Account).filter_by(email=setup["email"]).one()
        access = db.get(AdminAccess, account.id)
        account_id = account.id
        credentials = (account.password_hash, account.recovery_hash, account.created_at)
        mfa = (access.secret_cipher, access.enabled, access.last_counter, access.setup_hash, access.setup_expires_at)
        verified_at = admins.now()
        db.add(AccountSecurity(account_id=account_id, verified_at=verified_at, verification_source="legacy_existing", credential_version=2))
        db.add(AccountProfile(account_id=account_id, display_name="Operator profile"))
        db.add(Login(token_hash=token_hash("synthetic-normal-login"), account_id=account_id, expires_at=admins.now() + timedelta(hours=1)))
        db.add(AccountActionToken(token_hash=token_hash("synthetic-reset"), account_id=account_id, purpose="reset", target_email=account.email, credential_version=2, expires_at=admins.now() + timedelta(minutes=30)))
        for purpose in ("verify", "reset", "change_email", "receipt", "password_changed"):
            db.add(EmailOutbox(account_id=account_id, recipient=account.email, purpose=purpose, payload_cipher="synthetic-encrypted-payload", expires_at=admins.now() + timedelta(hours=1)))
        session = Session(owner_id=account_id, owner_token_hash=token_hash("synthetic-owned-session"))
        db.add(session)
        db.flush()
        application = Application(session_id=session.id, title="Owned application", data_json='{"cv":"Owned document"}')
        db.add(application)
        db.commit()
        session_id, application_id = session.id, application.id
    with factory() as db:
        assert admins.rename_email(db, "  ADMIN@EXAMPLE.COM  ", " INFO@TAFOLLI.NET ") == account_id
    with factory() as db:
        account = db.get(Account, account_id)
        access = db.get(AdminAccess, account_id)
        assert account.email == "info@tafolli.net"
        assert (account.password_hash, account.recovery_hash, account.created_at) == credentials
        assert (access.secret_cipher, access.enabled, access.last_counter, access.setup_hash, access.setup_expires_at) == mfa
        security = db.get(AccountSecurity, account_id)
        assert security.credential_version == 3
        assert (security.verified_at, security.verification_source) == (verified_at, "legacy_existing")
        assert db.get(AccountProfile, account_id).display_name == "Operator profile"
        assert db.get(Session, session_id).owner_id == account_id
        assert db.get(Application, application_id).data_json == '{"cv":"Owned document"}'
        assert db.query(AdminLogin).count() == db.query(Login).count() == db.query(AccountActionToken).count() == 0
        for row in db.query(EmailOutbox).all():
            if row.purpose in ("verify", "reset", "change_email"):
                assert row.status == "failed" and row.payload_cipher is None
            else:
                assert row.status == "pending" and row.payload_cipher == "synthetic-encrypted-payload"
                assert row.recipient == setup["email"]
        assert db.query(AdminAudit).filter_by(admin_id=account_id, action="admin.cli.email_changed").count() == 1
    assert client.get("/api/admin/me").status_code == 401
    clock[0] += 30
    credentials = {"email": setup["email"], "password": PASSWORD, "code": admins.totp(secret, clock[0] // 30)}
    assert client.post("/api/admin/login", json=credentials).status_code == 401
    renamed = client.post("/api/admin/login", json={**credentials, "email": "info@tafolli.net"})
    assert renamed.status_code == 200
    assert renamed.json()["email"] == "info@tafolli.net"
    assert client.get("/api/admin/me").json()["email"] == "info@tafolli.net"


def test_admin_email_correction_rejects_occupied_target_without_merging_or_revoking(env):
    client, factory, setup, _clock, _path = env
    complete(env)
    with factory() as db:
        occupied = Account(email="info@tafolli.net", password_hash="normal-user-hash", recovery_hash="normal-user-recovery")
        db.add(occupied)
        db.commit()
        occupied_id = occupied.id
    with factory() as db:
        with pytest.raises(ValueError, match="bereits belegt"):
            admins.rename_email(db, setup["email"], "info@tafolli.net")
        assert db.query(Account).filter_by(email=setup["email"]).count() == 1
        assert db.get(Account, occupied_id).password_hash == "normal-user-hash"
        assert db.get(AdminAccess, occupied_id) is None
        assert db.query(AdminLogin).count() == 1
        assert db.query(AdminAudit).filter_by(action="admin.cli.email_changed").count() == 0
    assert client.get("/api/admin/me").json()["email"] == setup["email"]


@pytest.mark.parametrize("source", ["ordinary@example.com", "missing@example.com", "admin@example.com"])
def test_admin_email_correction_refuses_non_admin_missing_or_inactive_source(env, source):
    _client, factory, _setup, _clock, _path = env
    with factory() as db:
        db.add(Account(email="ordinary@example.com", password_hash="ordinary-hash", recovery_hash="ordinary-recovery"))
        db.commit()
    with factory() as db:
        with pytest.raises(ValueError, match="aktiven Adminkonto"):
            admins.rename_email(db, source, "info@tafolli.net")
        assert db.query(Account).filter_by(email="info@tafolli.net").count() == 0
        assert db.query(AdminAccess).count() == 1
        assert not db.query(AdminAccess).one().enabled
        assert db.query(AdminAudit).filter_by(action="admin.cli.email_changed").count() == 0


@pytest.mark.parametrize("target", [" ADMIN@EXAMPLE.COM ", "bad-email", "name..part@example.com", "Name <admin@example.com>"])
def test_admin_email_correction_rejects_unchanged_or_invalid_address(env, target):
    _client, factory, setup, _clock, _path = env
    complete(env)
    with factory() as db:
        with pytest.raises(ValueError):
            admins.rename_email(db, setup["email"], target)
        assert db.query(Account).filter_by(email=setup["email"]).count() == 1
        assert db.query(AdminLogin).count() == 1


def test_admin_cli_email_correction_cannot_be_combined_with_credential_reset(monkeypatch):
    import sys

    from backend.manage_admin import main

    monkeypatch.setattr(sys, "argv", ["manage_admin", "--email", "info@tafolli.net", "--rename-from", "old@example.com", "--reset-existing"])
    with pytest.raises(SystemExit) as rejected:
        main()
    assert rejected.value.code == 2


def test_password_work_factor_upgrade_and_malformed_hashes(env):
    import hashlib

    from backend.services.account_service import migrate_existing_accounts, password_matches

    client, factory, _setup, _clock, _path = env
    salt = secrets.token_hex(16)
    legacy = (
        salt
        + ":"
        + hashlib.scrypt(PASSWORD.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    )
    assert password_matches(PASSWORD, legacy)
    assert not password_matches(PASSWORD, "malformed")
    with factory() as db:
        db.add(
            Account(
                email="legacy@example.com",
                password_hash=legacy,
                recovery_hash=token_hash("legacy-test"),
            )
        )
        db.commit()
    migrate_existing_accounts(factory.kw["bind"])
    assert (
        client.post(
            "/api/account/login", json={"email": "legacy@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )
    with factory() as db:
        assert (
            db.query(Account)
            .filter_by(email="legacy@example.com")
            .one()
            .password_hash.startswith("scrypt$32768$8$3$")
        )


def test_admin_verification_and_mail_statistics_reveal_metadata_only(env):
    from backend.account_models import AccountProfile, AccountSecurity, EmailOutbox

    client, factory, _setup, _clock, _path = env
    complete(env)
    with factory() as db:
        pending_account = Account(email="pending@example.com", password_hash="hidden-pending-hash", recovery_hash="hidden-recovery")
        verified_account = Account(email="confirmed@example.com", password_hash="hidden-verified-hash", recovery_hash="hidden-recovery")
        db.add_all([pending_account, verified_account])
        db.flush()
        db.add_all([
            AccountSecurity(account_id=pending_account.id, verification_source="email_pending"),
            AccountSecurity(account_id=verified_account.id, verification_source="email_confirmed", verified_at=admins.now()),
            AccountProfile(account_id=pending_account.id, display_name="Pending profile"),
            AccountProfile(account_id=verified_account.id, display_name="Confirmed profile"),
        ])
        for status in ("pending", "sent", "failed"):
            db.add(EmailOutbox(account_id=pending_account.id, recipient=pending_account.email,
                purpose="verify", status=status, payload_cipher="never-disclose-mail-payload",
                expires_at=admins.now() + timedelta(hours=24)))
        db.commit()
        pending_id = pending_account.id
    overview = client.get("/api/admin/overview")
    assert overview.status_code == 200
    assert overview.json()["totals"]["pending_verifications"] == 1
    assert overview.json()["totals"]["verified_users"] == 1
    assert overview.json()["email_delivery"]["pending"] == 1
    assert overview.json()["email_delivery"]["failed"] == 1
    assert overview.json()["email_delivery"]["sent"] == 1
    users = client.get("/api/admin/users")
    row = next(value for value in users.json()["items"] if value["id"] == pending_id)
    assert row["display_name"] == "Pending profile"
    assert row["verified_at"] is None and row["verification_source"] == "email_pending"
    detail = client.get("/api/admin/users/" + pending_id)
    assert detail.json()["display_name"] == "Pending profile"
    for response in (overview, users, detail, client.get("/api/admin/database")):
        assert "never-disclose-mail-payload" not in response.text
        assert "hidden-pending-hash" not in response.text
        assert "payload_cipher" not in response.text and "credential_version" not in response.text
