import io
import json
import socket
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.llm.base import LLMResult
from backend.llm.http_provider import (
    PROVIDERS,
    HTTPProvider,
    request_payload,
    response_text,
)
from backend.main import app
from backend.services import application_service, job_service

SOURCE = "# Alex Source\nDeveloper\nalex@example.com\n\n## Experience\nExample Company 2020–2025\n- Built reports in Excel.\n\n## Education\nB.Sc. Example University\n"
JOB = {
    "description": "We need React Kubernetes and Terraform development.",
    "title": "Developer",
    "company": "Example Corp",
}


def session(client):
    value = client.post("/api/session").json()
    client.headers["X-Session-Token"] = value["session_token"]
    return value["session_id"]


def package_body(client):
    sid = session(client)
    profile = application_service.parse_profile(SOURCE)
    profile["confirmed"] = True
    return {
        "session_id": sid,
        "profile": profile,
        "job": JOB,
        "demo": True,
        "provider": "openai",
    }


def register(client):
    email = f"{uuid.uuid4()}@example.com"
    value = client.post(
        "/api/account/register",
        json={"email": email, "password": "test-long-password-123"},
    )
    assert value.status_code == 200, value.text
    return value.json()


def test_session_id_does_not_grant_access():
    owner, stranger = TestClient(app), TestClient(app)
    sid = session(owner)
    data = {"session_id": sid, "job_description": "Long enough job description."}
    assert stranger.post("/api/generate", json=data).status_code == 403
    assert stranger.delete("/api/session/" + sid).status_code == 403
    assert owner.delete("/api/session/" + sid).status_code == 200
    assert owner.post("/api/generate", json=data).status_code == 404


def test_chunked_requests_cannot_bypass_upload_limit():
    client = TestClient(app)
    body = iter([b'{"text":"', b"a" * (12 * 1024 * 1024), b'"}'])
    response = client.post(
        "/api/profile/parse", content=body, headers={"Content-Type": "application/json"}
    )
    assert "content-length" not in response.request.headers
    assert response.status_code == 413, response.text


def test_explicit_demo_full_package_and_confirmation():
    client = TestClient(app)
    body = package_body(client)
    body["profile"]["confirmed"] = False
    assert client.post("/api/package", json=body).status_code == 422
    body["profile"]["confirmed"] = True
    response = client.post("/api/package", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data["documents"]) == {
        "cv",
        "cover_letter",
        "motivation_letter",
        "email",
    }
    assert "Kubernetes" not in data["documents"]["cv"]
    assert "Example University" in data["documents"]["cv"]
    assert data["is_demo"] is True
    assert "Betreff:" in data["documents"]["email"]
    body["demo"] = False
    assert client.post("/api/package", json=body).status_code == 422


def test_profile_overlong_and_upload_limits():
    client = TestClient(app)
    sid = session(client)
    assert client.post("/api/profile/parse", json={"source_text": "a" * 60001}).status_code == 422
    assert (
        client.post(
            "/api/upload-cv",
            data={"session_id": sid},
            files={"file": ("cv.txt", b"a" * 60001)},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/upload-cv",
            data={"session_id": sid},
            files={"file": ("cv.txt", b"a" * (11 * 1024 * 1024))},
        ).status_code
        == 413
    )
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"a" * (26 * 1024 * 1024))
    result = client.post(
        "/api/upload-cv",
        data={"session_id": sid},
        files={"file": ("bomb.docx", memory.getvalue())},
    )
    assert result.status_code == 422


def test_provider_contracts_and_truncation():
    messages = [{"role": "user", "content": "Source facts"}]
    for name in PROVIDERS:
        options = (
            {"model": "my-deployment", "endpoint": "https://example.openai.azure.com"}
            if name == "azure"
            else {}
        )
        url, headers, body = request_payload(name, "synthetic-key", "System", messages, **options)
        assert "synthetic-key" not in url
        if name == "claude":
            assert body["system"] == "System"
            assert headers["x-api-key"] == "synthetic-key"
            data = {"content": [{"type": "text", "text": "# Resume"}]}
        elif name == "gemini":
            assert body["contents"][0]["role"] == "user"
            assert "generateContent" in url
            data = {"candidates": [{"content": {"parts": [{"text": "# Resume"}]}}]}
        else:
            assert url.endswith("/responses")
            assert body["store"] is False
            assert "max_tokens" not in body
            data = {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "# Resume"}],
                    }
                ]
            }
        assert response_text(name, data) == "# Resume"
    with pytest.raises(HTTPException):
        response_text("openai", {"status": "incomplete"})
    with pytest.raises(HTTPException):
        request_payload(
            "azure",
            "key",
            "system",
            [],
            model="deployment",
            endpoint="https://127.0.0.1",
        )


def test_provider_failure_never_becomes_demo(monkeypatch):
    def reject(self, system, messages, **kwargs):
        raise HTTPException(502, "Provider unavailable")

    monkeypatch.setattr(HTTPProvider, "generate", reject)
    client = TestClient(app)
    body = package_body(client)
    body.update(demo=False, keys={"openai": "synthetic-key"})
    response = client.post("/api/package", json=body)
    assert response.status_code == 502
    assert "documents" not in response.json()


def test_every_refinement_keeps_the_original_source(monkeypatch):
    messages_seen = []

    def generate(self, system, messages, **kwargs):
        messages_seen.append(messages)
        return LLMResult("# Alex Source\nDeveloper\nRevised from source.", self.name, "test-model")

    monkeypatch.setattr(HTTPProvider, "generate", generate)
    client = TestClient(app)
    body = package_body(client)
    body.update(
        demo=False,
        keys={"openai": "synthetic-key"},
        document="cv",
        current_content="# Alex Source\nCurrent draft long enough",
        instruction="Make concise",
    )
    for _ in range(3):
        result = client.post("/api/package/refine", json=body)
        assert result.status_code == 200, result.text
        body["current_content"] = result.json()["content"]
    for messages in messages_seen:
        value = json.loads(messages[0]["content"])
        assert value["confirmed_profile"]["source_text"] == SOURCE
        assert value["job"]["description"] == JOB["description"]


def test_invalid_model_package_rejected(monkeypatch):
    monkeypatch.setattr(
        HTTPProvider,
        "generate",
        lambda *args, **kwargs: LLMResult('{"cv":"partial resume"}', "openai", "test-model"),
    )
    client = TestClient(app)
    body = package_body(client)
    body.update(demo=False, keys={"openai": "synthetic-key"})
    assert client.post("/api/package", json=body).status_code == 502


def test_owned_project_crud_recovery_and_account_deletion():
    owner, stranger = TestClient(app), TestClient(app)
    account = register(owner)
    register(stranger)
    body = package_body(owner)
    documents = owner.post("/api/package", json=body).json()["documents"]
    project = {
        "session_id": body["session_id"],
        "profile": body["profile"],
        "job": body["job"],
        "documents": documents,
        "title": "Example job",
        "status": "draft",
    }
    pid = owner.post("/api/projects", json=project).json()["id"]
    assert len(owner.get("/api/projects").json()) == 1
    assert stranger.get("/api/projects/" + pid).status_code == 404
    assert stranger.delete("/api/projects/" + pid).status_code == 404
    project["status"] = "interview"
    assert owner.put("/api/projects/" + pid, json=project).status_code == 200
    assert owner.get("/api/projects/" + pid).json()["status"] == "interview"
    assert owner.post("/api/account/logout", json={}).status_code == 200
    assert owner.get("/api/projects").status_code == 401
    recovered = owner.post(
        "/api/account/recover",
        json={
            "email": account["email"],
            "password": "new-test-password-123",
            "recovery_code": account["recovery_code"],
        },
    )
    assert recovered.status_code == 200
    assert (
        owner.post(
            "/api/account/recover",
            json={
                "email": account["email"],
                "password": "new-test-password-123",
                "recovery_code": account["recovery_code"],
            },
        ).status_code
        == 401
    )
    assert (
        owner.post(
            "/api/account/login",
            json={"email": account["email"], "password": "new-test-password-123"},
        ).status_code
        == 200
    )
    assert owner.delete("/api/account").status_code == 200
    assert owner.get("/api/projects").status_code == 401


def test_cleanup_removes_expired_anonymous_data_but_keeps_account_projects():
    from backend.cleanup import cleanup
    from backend.database import SessionLocal
    from backend.models import Account, Login, Session

    owner = TestClient(app)
    account = register(owner)
    body = package_body(owner)
    documents = owner.post("/api/package", json=body).json()["documents"]
    project = {
        "session_id": body["session_id"],
        "profile": body["profile"],
        "job": body["job"],
        "documents": documents,
        "title": "Retained account application",
        "status": "draft",
    }
    pid = owner.post("/api/projects", json=project).json()["id"]
    anonymous_id = session(TestClient(app))
    expired = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=40)
    with SessionLocal() as db:
        db.get(Session, anonymous_id).created_at = expired
        db.get(Session, body["session_id"]).created_at = expired
        account_id = db.query(Account).filter_by(email=account["email"]).one().id
        db.add(Login(token_hash="expired-test-token", account_id=account_id, expires_at=expired))
        db.commit()
    cleanup()
    with SessionLocal() as db:
        assert db.get(Session, anonymous_id) is None
        assert db.get(Session, body["session_id"]) is not None
        assert db.get(Login, "expired-test-token") is None
    assert owner.get("/api/projects/" + pid).status_code == 200
    assert owner.delete("/api/account").status_code == 200


def test_public_job_import_rejects_internal_networks(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    for url in (
        "https://localhost/job",
        "https://public.example/job",
        "file:///etc/passwd",
        "http://169.254.169.254",
        "https://name:password@example.com",
    ):
        with pytest.raises(HTTPException):
            job_service.public_address(url)


def test_jobposting_extraction_uses_structure_and_marks_review(monkeypatch):
    html = (
        '<html><script type="application/ld+json">'
        + json.dumps(
            {
                "@graph": [
                    {
                        "@type": "JobPosting",
                        "title": "Developer",
                        "hiringOrganization": {"name": "Example"},
                        "description": "<p>Write React interfaces and reliable tests.</p>",
                    }
                ]
            }
        )
        + "</script><script>secret instructions</script></html>"
    )
    monkeypatch.setattr(job_service, "fetch_page", lambda url: (html, url))
    result = job_service.import_job("https://example.com/job")
    assert result["company"] == "Example"
    assert result["description"] == "Write React interfaces and reliable tests."
    assert result["needs_review"] is True


def test_cross_origin_write_rejected_and_sensitive_no_store():
    client = TestClient(app)
    assert (
        client.post("/api/session", headers={"Origin": "https://malicious.example"}).status_code
        == 403
    )
    assert client.post("/api/session", headers={"Origin": "http://testserver"}).status_code == 200
    assert client.get("/api/account").headers["cache-control"] == "no-store"
    assert "frame-ancestors" in client.get("/").headers["content-security-policy"]


def test_api_abuse_limit():
    client = TestClient(app)
    for _ in range(10):
        client.post(
            "/api/account/login",
            json={"email": "invalid", "password": "long-test-password"},
        )
    assert (
        client.post(
            "/api/account/login",
            json={"email": "invalid", "password": "long-test-password"},
        ).status_code
        == 429
    )


def test_boosty_requires_consent_ownership_and_own_key(monkeypatch):
    seen = []

    def answer(self, system, messages, **_kwargs):
        seen.append((system, messages))
        return LLMResult("Follow the four steps.", self.name, "test-model")

    monkeypatch.setattr(HTTPProvider, "generate", answer)
    client = TestClient(app)
    sid = session(client)
    body = {
        "session_id": sid,
        "question": "How do I save?",
        "provider": "openai",
        "keys": {"openai": "synthetic-key"},
    }
    assert client.post("/api/assistant", json=body).status_code == 422
    body["consent"] = True
    stranger = TestClient(app)
    assert stranger.post("/api/assistant", json=body).status_code == 403
    assert client.post("/api/assistant", json={**body, "keys": {}}).status_code == 422
    result = client.post("/api/assistant", json=body)
    assert result.status_code == 200 and result.json()["model"] == "test-model"
    assert seen[0][1] == [{"role": "user", "content": "Language: de\nQuestion: How do I save?"}]
    assert SOURCE not in seen[0][0] and "synthetic-key" not in str(seen)


def test_usage_is_metadata_only_and_account_deletion_unlinks_events():
    from backend.database import SessionLocal
    from backend.models import Account, Activity

    client = TestClient(app)
    value = register(client)
    sid = session(client)
    assert (
        client.post("/api/usage", json={"session_id": sid, "event": "demo.generate"}).status_code
        == 200
    )
    assert (
        client.post("/api/usage", json={"session_id": sid, "event": "password.secret"}).status_code
        == 422
    )
    with SessionLocal() as db:
        account = db.query(Account).filter_by(email=value["email"]).one()
        aid = account.id
        rows = db.query(Activity).filter_by(account_id=aid).all()
        assert {r.event for r in rows} >= {"account.register", "session.start", "demo.generate"}
    assert client.delete("/api/account").status_code == 200
    with SessionLocal() as db:
        assert db.query(Activity).filter_by(account_id=aid).count() == 0


def test_analytics_and_admin_retention_is_bounded():
    from backend.cleanup import cleanup
    from backend.database import SessionLocal
    from backend.models import Activity, AdminAudit, AdminLogin, DailyMetric

    now = datetime.now(UTC).replace(tzinfo=None)
    with SessionLocal() as db:
        old_event = Activity(
            event="retention.test", outcome=200, created_at=now - timedelta(days=31)
        )
        fresh_event = Activity(event="retention.test", outcome=200, created_at=now)
        old_audit = AdminAudit(action="retention.test", created_at=now - timedelta(days=91))
        fresh_audit = AdminAudit(action="retention.test", created_at=now)
        day = (now - timedelta(days=91)).date().isoformat()
        if not db.get(DailyMetric, day):
            db.add(DailyMetric(day=day, page_views=1, visits=1))
        db.add_all([old_event, fresh_event, old_audit, fresh_audit])
        db.commit()
        ids = [old_event.id, fresh_event.id, old_audit.id, fresh_audit.id]
    cleanup()
    with SessionLocal() as db:
        assert db.get(Activity, ids[0]) is None and db.get(Activity, ids[1])
        assert db.get(AdminAudit, ids[2]) is None and db.get(AdminAudit, ids[3])
        assert db.get(DailyMetric, day) is None
        assert db.query(AdminLogin).filter(AdminLogin.expires_at <= now).count() == 0


def test_app_shell_assets_and_worker_share_a_version():
    import re

    client = TestClient(app)
    index = client.get("/")
    admin = client.get("/admin")
    version = re.search(r"professional.css\?v=([a-f0-9]{12})", index.text)[1]
    assert f"professional.css?v={version}" in admin.text
    assert index.headers["cache-control"] == "no-cache"
    worker = client.get("/sw.js").text
    assert "__BUILD_ID__" not in worker
    assert f"boosty-shell-{version}" in worker
    assert f"app.js?v={version}" in worker
    assert "clients.claim" in worker
    assert "endsWith('/admin')" in worker
