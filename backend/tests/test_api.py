"""API-Tests (pytest + FastAPI TestClient).

Laufen komplett offline: ohne API-Keys antwortet die App im Demo-Modus.
Start:  pytest backend/tests -v
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


@pytest.fixture()
def session_id() -> str:
    r = client.post("/api/session?language=de")
    assert r.status_code == 200
    return r.json()["session_id"]


def test_status():
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["app"]
    assert set(body["providers"].keys()) == {"claude", "openai"}
    assert body["rag_mode"] in ("embeddings", "tfidf")


def test_create_session():
    r = client.post("/api/session?language=en")
    assert r.status_code == 200
    body = r.json()
    assert body["language"] == "en"
    assert body["has_cv"] is False


def test_upload_cv_txt(session_id):
    cv = b"Max Mustermann\nKoch\nmax@example.com | 0151 1234567\n\n10 Jahre Erfahrung in der Gastronomie."
    r = client.post(
        "/api/upload-cv",
        data={"session_id": session_id},
        files={"file": ("cv.txt", cv, "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["characters"] > 0
    assert body["chunks"] >= 1
    assert body["rag_mode"] in ("embeddings", "tfidf")


def test_upload_rejects_unknown_format(session_id):
    r = client.post(
        "/api/upload-cv",
        data={"session_id": session_id},
        files={"file": ("cv.xyz", b"abc", "application/octet-stream")},
    )
    assert r.status_code == 422


def test_generate_demo_mode(session_id):
    r = client.post(
        "/api/generate",
        json={
            "session_id": session_id,
            "job_description": "Wir suchen eine/n Koch (m/w/d) mit HACCP-Kenntnissen.",
            "provider": "claude",
            "language": "de",
            "technique": "auto",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "single"
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["content"]
    assert 0.0 <= result["analysis"]["ats_score"] <= 100.0


def test_refine_requires_generation(session_id):
    r = client.post(
        "/api/refine",
        json={
            "session_id": session_id,
            "instruction": "kürzer",
            "provider": "claude",
            "language": "de",
        },
    )
    assert r.status_code == 409


def test_export_pdf():
    r = client.post(
        "/api/export",
        json={
            "content": "# Max Mustermann\nKoch\n\n## Profil\nErfahrener Koch.",
            "format": "pdf",
            "design": "modern",
            "language": "de",
            "filename": "Lebenslauf",
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_export_rejects_bad_format():
    r = client.post(
        "/api/export",
        json={"content": "# Test CV lang genug", "format": "exe"},
    )
    assert r.status_code == 422


def test_unknown_session_returns_404():
    r = client.post(
        "/api/generate",
        json={
            "session_id": "00000000-0000-0000-0000-000000000000",
            "job_description": "Eine ausreichend lange Stellenbeschreibung.",
        },
    )
    assert r.status_code == 404
