"""Account-owned drafts survive login; history never exposes another user's content."""

from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.platform import Job, Profile
from backend.services.application_service import demo_package, parse_profile
from backend.tests.test_platform import JOB, SOURCE, register, session


def test_draft_promotes_to_package_and_survives_relogin():
    owner, stranger = TestClient(app), TestClient(app)
    account = register(owner)
    register(stranger)
    sid = session(owner)
    body = {
        "session_id": sid,
        "title": "Example Corp · Developer",
        "profile": {"source_text": "", "name": "Alex Example"},
        "job": {"description": "", "company": "Example Corp", "title": "Developer"},
        "documents": None,
        "wishes": "Use concise language",
        "step": 2,
        "design": "sapphire",
        "photo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII=",
    }
    saved = owner.post("/api/projects", json=body)
    assert saved.status_code == 200, saved.text
    pid, revision = saved.json()["id"], saved.json()["revision"]
    draft = owner.get("/api/projects/" + pid).json()
    assert draft["documents"] is None and draft["wishes"] == body["wishes"]
    assert draft["_generated_at"] is None and draft["_created_at"]
    profile = parse_profile(SOURCE)
    body.update(
        profile=profile,
        job=JOB,
        documents=demo_package(Profile(**profile), Job(**JOB), "de"),
        revision=revision,
        status="ready",
        step=4,
    )
    updated = owner.put("/api/projects/" + pid, json=body)
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == revision + 1
    stale = owner.put("/api/projects/" + pid, json={**body, "title": "Stale tab"})
    assert stale.status_code == 409
    assert (
        owner.put(
            "/api/projects/" + pid, json={k: v for k, v in body.items() if k != "revision"}
        ).status_code
        == 409
    )
    assert owner.get("/api/projects/" + pid).json()["title"] == body["title"]
    history = owner.get("/api/projects").json()
    row = next(p for p in history if p["id"] == pid)
    assert row["company"] == JOB["company"] and row["role"] == JOB["title"]
    assert row["has_documents"] and row["generated_at"]
    assert row["created_at"] == draft["_created_at"]
    assert stranger.get("/api/projects/" + pid).status_code == 404
    assert stranger.put("/api/projects/" + pid, json=body).status_code == 404
    assert not any(p["id"] == pid for p in stranger.get("/api/projects").json())
    owner.post("/api/account/logout", json={})
    assert owner.get("/api/projects").status_code == 401
    assert (
        owner.post(
            "/api/account/login",
            json={"email": account["email"], "password": "test-long-password-123"},
        ).status_code
        == 200
    )
    restored = owner.get("/api/projects/" + pid).json()
    assert restored["documents"] == body["documents"] and restored["design"] == "sapphire"
    assert restored["wishes"] == body["wishes"]
    assert restored["photo"] == body["photo"]
    owner.request("DELETE", "/api/account", json={"current_password": "test-long-password-123", "confirmation": "DELETE"})
    stranger.request("DELETE", "/api/account", json={"current_password": "test-long-password-123", "confirmation": "DELETE"})


def test_saved_projects_reject_credentials_active_images_and_partial_documents():
    owner = TestClient(app)
    register(owner)
    body = {"session_id": session(owner), "title": "Draft", "profile": {}, "job": {}}
    assert (
        owner.post(
            "/api/projects", json={**body, "keys": {"openai": "synthetic-secret"}}
        ).status_code
        == 422
    )
    assert (
        owner.post(
            "/api/projects", json={**body, "profile": {"password": "synthetic-password"}}
        ).status_code
        == 422
    )
    assert (
        owner.post(
            "/api/projects", json={**body, "photo": "data:image/svg+xml;base64,PHN2Zz4="}
        ).status_code
        == 422
    )
    assert (
        owner.post("/api/projects", json={**body, "documents": {"cv": "partial"}}).status_code
        == 422
    )
    assert TestClient(app).post("/api/projects", json=body).status_code == 401
    owner.request("DELETE", "/api/account", json={"current_password": "test-long-password-123", "confirmation": "DELETE"})


def test_concurrent_edits_cannot_overwrite_the_same_revision():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    owner = TestClient(app)
    register(owner)
    body = {"session_id": session(owner), "title": "Draft", "profile": {}, "job": {}}
    result = owner.post("/api/projects", json=body).json()
    gate = Barrier(2)

    def write(title):
        client = TestClient(app)
        client.cookies.update(owner.cookies)
        gate.wait()
        return client.put(
            "/api/projects/" + result["id"],
            json={**body, "title": title, "revision": result["revision"]},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(write, ["First tab", "Second tab"]))
    assert sorted(outcomes) == [200, 409]
    assert owner.get("/api/projects/" + result["id"]).json()["_revision"] == 2
    owner.request("DELETE", "/api/account", json={"current_password": "test-long-password-123", "confirmation": "DELETE"})


def test_boosty_rejects_accidental_credentials_before_provider_call(monkeypatch):
    from backend.services import boosty_service

    owner = TestClient(app)
    sid = session(owner)
    calls = []
    monkeypatch.setattr(boosty_service, "enabled", lambda: True)
    monkeypatch.setattr(boosty_service, "classify", lambda q: calls.append(q) or "unknown")
    for text in ["sk-" + "a" * 30, "xai-" + "a" * 30, "Passwort: synthetic-secret"]:
        response = owner.post(
            "/api/assistant", json={"session_id": sid, "question": text, "consent": True}
        )
        assert response.status_code == 422
    assert not calls
    owner.delete("/api/session/" + sid)
