"""Administrative authorization, MFA, protected data access and retention boundaries."""

import json
import re
import secrets
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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


def test_admin_never_granted_by_public_registration_or_email(env):
    client, factory, setup, _clock, _path = env
    assert (
        client.post(
            "/api/account/register", json={"email": setup["email"], "password": PASSWORD}
        ).status_code
        == 409
    )
    normal = client.post(
        "/api/account/register",
        json={
            "email": "normal@example.com",
            "password": PASSWORD,
            "is_admin": True,
            "role": "admin",
        },
    )
    assert normal.status_code == 200
    for route in ("overview", "users", "events", "audit", "database", "sessions"):
        assert client.get("/api/admin/" + route).status_code == 401
    client.headers["Authorization"] = "Bearer " + normal.json()["access_token"]
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
        == 401
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


def test_password_work_factor_upgrade_and_malformed_hashes(env):
    import hashlib

    from backend.services.account_service import password_matches

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
