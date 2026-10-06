"""Verify real on-disk account/project persistence across independent processes."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_registration_and_projects_survive_restart(tmp_path):
    database = tmp_path / "nested" / "accounts.db"
    environment = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + str(database),
        "SECURE_COOKIES": "true",
        "ALLOWED_HOSTS": "testserver",
        "ALLOW_SERVER_KEYS": "false",
        "TEST_BACKUP_DIR": str(tmp_path / "backups"),
        "MAIL_KEY_FILE": str(tmp_path / "mail.key"),
    }
    common = """
from fastapi.testclient import TestClient
from backend.main import app
client = TestClient(app, base_url="https://testserver")
credentials = {"email":"persistence@example.invalid", "password":"synthetic-test-password-123"}
from unittest.mock import patch
import json
from backend.account_terms import TERMS_VERSION
from backend.account_models import EmailOutbox
from backend.database import SessionLocal
from backend.services import account_mail
consent = {"terms_accepted":True,"privacy_acknowledged":True,"terms_version":TERMS_VERSION}
def register_verified(target,email):
    with patch.object(account_mail,"ready",return_value=True):
        response = target.post("/api/account/register",json={**credentials,**consent,"email":email})
    assert response.status_code==200,response.text
    with SessionLocal() as db:
        row=db.query(EmailOutbox).filter_by(recipient=email,purpose="verify").one()
        token=json.loads(account_mail.cipher().decrypt(row.payload_cipher.encode()))["token"]
    with patch.object(account_mail,"ready",return_value=True):
        assert target.post("/api/account/verify-email",json={"token":token}).status_code==200
    return target.post("/api/account/login",json={**credentials,"email":email})
"""
    first = (
        common
        + """
response = register_verified(client,credentials["email"])
assert response.status_code == 200, response.text
cookie = response.headers["set-cookie"].lower()
assert "httponly" in cookie and "secure" in cookie
session = client.post("/api/session").json()
client.headers["X-Session-Token"] = session["session_token"]
data = {
    "session_id": session["session_id"], "title":"Persistent application", "status":"ready",
    "profile":{"name":"Synthetic Example", "source_text":"Synthetic resume with original facts.", "confirmed":True},
    "job":{"title":"Developer", "company":"Example", "description":"We need a developer with proven experience."},
    "documents":{key:"Synthetic document with original facts." for key in ["cv","cover_letter","motivation_letter","email"]},
    "notes":"Persisted notes"
}
result = client.post("/api/projects",json=data)
assert result.status_code == 200,result.text
assert client.post("/api/account/logout",json={}).status_code == 200
assert client.get("/api/projects").status_code == 401
print(result.json()["id"])
"""
    )
    created = subprocess.run(
        [sys.executable, "-c", first],
        env=environment,
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    environment["TEST_PROJECT_ID"] = created.stdout.strip()
    second = (
        common
        + """
import os
from pathlib import Path
from backend.manage_database import backup_database
assert client.post("/api/account/login",json={**credentials,"password":"incorrect-password-123"}).status_code == 401
assert client.post("/api/account/login",json=credentials).status_code == 200
assert client.get("/api/account").json()["email"] == credentials["email"]
projects = client.get("/api/projects").json()
assert len(projects) == 1 and projects[0]["id"] == os.environ["TEST_PROJECT_ID"]
project = client.get("/api/projects/"+projects[0]["id"]).json()
assert project["status"] == "ready" and project["notes"] == "Persisted notes"
assert project["profile"]["source_text"] == "Synthetic resume with original facts."
stranger = TestClient(app,base_url="https://testserver")
assert register_verified(stranger,"stranger@example.invalid").status_code == 200
assert stranger.get("/api/projects/"+projects[0]["id"]).status_code == 404
backup_database(Path(os.environ["TEST_BACKUP_DIR"]))
"""
    )
    subprocess.run(
        [sys.executable, "-c", second],
        env=environment,
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        stored = connection.execute("SELECT password_hash FROM accounts LIMIT 1").fetchone()[0]
        assert "synthetic-test-password" not in stored
    backup = next((tmp_path / "backups").glob("*.db"))
    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 1
    if os.name != "nt":
        assert database.stat().st_mode & 0o777 == 0o600
        assert backup.stat().st_mode & 0o777 == 0o600


def test_admin_mfa_and_sessions_survive_restart(tmp_path):
    environment = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + str(tmp_path / "admin.db"),
        "ADMIN_KEY_FILE": str(tmp_path / "admin.key"),
        "SECURE_COOKIES": "true",
        "TEST_PRIVATE_DIR": str(tmp_path / "private"),
        "TEST_TOKEN_FILE": str(tmp_path / "token"),
    }
    common = """
import os, re
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import AdminAccess
from backend.services import admin_service as admins
client=TestClient(app,base_url="https://testserver",headers={"X-Boosty-Request":"1"})
"""
    first = (
        common
        + """
with SessionLocal() as db:
    file=admins.provision(db,"restart-admin@example.invalid",Path(os.environ["TEST_PRIVATE_DIR"]))
setup={"email":"restart-admin@example.invalid","setup_code":re.search(r"Einrichtungscode: (\\S+)",file.read_text())[1]}
secret=client.post("/api/admin/setup/begin",json=setup).json()["secret"]
response=client.post("/api/admin/setup/finish",json={**setup,"password":"synthetic-test-password-1234","code":admins.totp(secret,int(admins.time.time())//30)})
assert response.status_code==200,response.text
Path(os.environ["TEST_TOKEN_FILE"]).write_text(response.json()["access_token"])
assert client.get("/api/admin/overview").status_code==200
"""
    )
    second = (
        common
        + """
client.headers["Authorization"]="Bearer "+Path(os.environ["TEST_TOKEN_FILE"]).read_text()
assert client.get("/api/admin/me").json()["email"]=="restart-admin@example.invalid"
assert client.get("/api/admin/database").status_code==200
with SessionLocal() as db:
    access=db.query(AdminAccess).one()
    secret=admins.cipher().decrypt(access.secret_cipher.encode()).decode()
    assert not admins.accept_totp(db,access,admins.totp(secret,access.last_counter))
assert client.post("/api/admin/logout",json={}).status_code==200
assert client.get("/api/admin/overview").status_code==401
"""
    )
    for script in (first, second):
        subprocess.run(
            [sys.executable, "-c", script],
            env=environment,
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
