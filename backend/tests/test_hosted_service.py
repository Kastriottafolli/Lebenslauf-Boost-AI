"""Mandatory accounts, operator-only credentials, budget limits and OAuth replay protection."""

import base64
import json
import secrets
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.database import SessionLocal
from backend.main import app
from backend.models import Account, AIBudget, AICall
from backend.routers import social
from backend.routers.platform import Job, Profile
from backend.services import hosted_ai
from backend.services.application_service import demo_package, parse_profile
from backend.tests.test_platform import JOB, SOURCE, register, session


@pytest.fixture
def hosted(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "hosted_ai_enabled", True)
    monkeypatch.setattr(s, "openai_api_key", "synthetic-private-operator-key")
    monkeypatch.setattr(s, "ai_global_daily_calls", 10000)
    monkeypatch.setattr(s, "ai_daily_budget_usd", 1000)
    return s


def payload(sid):
    return {
        "session_id": sid,
        "profile": {**parse_profile(SOURCE), "confirmed": True},
        "job": JOB,
        "consent": True,
    }


def test_anonymous_cannot_import_generate_or_bypass_old_endpoints(hosted):
    client = TestClient(app)
    sid = session(client)
    for path, body in [
        ("/api/package", payload(sid)),
        ("/api/assistant", {"session_id": sid, "question": "Help", "consent": True}),
        ("/api/job/import", {"url": "https://example.com/job"}),
        ("/api/generate", {}),
        ("/api/provider/test", {}),
    ]:
        assert client.post(path, json=body).status_code == 401, path
    assert client.get("/api/hosted-config").status_code == 200
    register(client)
    for path in ["/api/generate", "/api/refine", "/api/provider/test"]:
        assert client.post(path, json={}).status_code == 410
    owned = session(client)
    stranger = TestClient(app)
    register(stranger)
    assert (
        stranger.post(
            "/api/package",
            json=payload(owned),
            headers={"X-Session-Token": client.headers["X-Session-Token"]},
        ).status_code
        == 403
    )
    # Authenticated requests must also own the session, not merely possess an old token.
    assert client.post("/api/package", json=payload(sid)).status_code == 403


def test_operator_key_only_structured_package_and_atomic_daily_limit(hosted, monkeypatch):
    client = TestClient(app)
    reg = register(client)
    sid = session(client)
    monkeypatch.setattr(hosted, "ai_account_daily_packages", 1)
    calls = []
    documents = demo_package(Profile(**parse_profile(SOURCE)), Job(**JOB), "de")

    class Network:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers, json):
            calls.append(json)
            assert headers["Authorization"] == "Bearer synthetic-private-operator-key"
            assert url == "https://api.openai.com/v1/responses"
            return httpx.Response(
                200,
                json={
                    "usage": {"input_tokens": 200, "output_tokens": 500},
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": __import__("json").dumps(documents)}
                            ],
                        }
                    ],
                },
            )

    monkeypatch.setattr(hosted_ai.httpx, "Client", Network)
    body = payload(sid)
    for forbidden in [
        {"provider": "grok"},
        {"keys": {"openai": "client-key"}},
        {"model": "expensive-model"},
        {"demo": True},
    ]:
        assert client.post("/api/package", json={**body, **forbidden}).status_code == 422
    assert client.post("/api/package", json={**body, "consent": False}).status_code == 422
    response = client.post("/api/package", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["is_demo"] is False
    assert calls[0]["store"] is False and calls[0]["text"]["format"]["strict"] is True
    assert client.post("/api/package", json=body).status_code == 429
    assert len(calls) == 1
    with SessionLocal() as db:
        account = db.query(Account).filter_by(email=reg["email"]).one()
        record = db.query(AICall).filter_by(account_id=account.id).one()
        assert (
            record.status == "success" and record.input_tokens == 200 and record.actual_microusd > 0
        )
    for path in ["/", "/api/hosted-config", "/api/assistant/config", "/api/oauth/providers"]:
        assert "synthetic-private-operator-key" not in client.get(path).text


def test_budget_failure_reservation_and_account_recreation_do_not_reset_global_cap(
    hosted, monkeypatch
):
    client = TestClient(app)
    info = register(client)
    with SessionLocal() as db:
        account = db.query(Account).filter_by(email=info["email"]).one()
        monkeypatch.setattr(hosted, "ai_daily_budget_usd", 0.000001)
        with pytest.raises(HTTPException) as error:
            hosted_ai.reserve(db, account, "package", "gpt-4.1-mini", 100, 10000)
        assert error.value.status_code == 429
        monkeypatch.setattr(hosted, "ai_daily_budget_usd", 1000)
        hosted_ai.reserve(db, account, "help", "gpt-4.1-mini", 100, 256)
        budget = db.query(AIBudget).order_by(AIBudget.day.desc()).first()
        before = (budget.calls, budget.reserved_microusd)
        db.delete(account)
        db.commit()
        db.refresh(budget)
        assert (budget.calls, budget.reserved_microusd) == before


def test_social_state_browser_binding_single_use_and_no_email_autolink(hosted, monkeypatch):
    monkeypatch.setattr(hosted, "oauth_base_url", "https://testserver")
    monkeypatch.setattr(hosted, "oauth_google_client_id", "synthetic-google-id")
    monkeypatch.setattr(hosted, "oauth_google_client_secret", "synthetic-google-secret")
    client = TestClient(app, base_url="https://testserver")
    start = client.get("/api/oauth/google/start", follow_redirects=False)
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"] and query["nonce"]
    assert "synthetic-google-secret" not in start.headers["location"]
    state = query["state"][0]
    endpoint = "/api/oauth/google/callback?" + "state=" + state + "&code=synthetic"
    assert TestClient(app, base_url="https://testserver").get(endpoint).status_code == 400
    email = secrets.token_hex(8) + "@example.com"
    monkeypatch.setattr(social, "exchange", lambda *args: ("google-" + email, email))
    assert client.get(endpoint, follow_redirects=False).status_code == 303
    assert client.get("/api/account").json()["email"] == email
    assert client.get(endpoint).status_code == 400
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as error:
            social.social_account(db, "apple", "different-subject", email)
        assert error.value.status_code == 409
    assert all(
        not p["enabled"]
        for p in TestClient(app).get("/api/oauth/providers").json()
        if p["id"] != "google"
    )


def test_oidc_signature_audience_nonce_and_expiry_are_verified():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    number = key.public_key().public_numbers()

    def encode(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    jwk = {
        "kid": "test-key",
        "kty": "RSA",
        "e": encode(number.e.to_bytes(3, "big")),
        "n": encode(number.n.to_bytes(256, "big")),
    }
    client = SimpleNamespace(
        get=lambda url: SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"keys": [jwk]})
    )
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "client",
        "sub": "subject",
        "nonce": "nonce",
        "email": "example@example.com",
        "email_verified": True,
        "exp": time.time() + 300,
        "iat": time.time(),
    }

    def token(value):
        data = (
            encode(json.dumps({"alg": "RS256", "kid": "test-key"}).encode())
            + "."
            + encode(json.dumps(value).encode())
        )
        return data + "." + encode(key.sign(data.encode(), padding.PKCS1v15(), hashes.SHA256()))

    assert social.verify_identity(token(claims), "google", "client", "nonce", client) == (
        "subject",
        "example@example.com",
    )
    for field, value in [
        ("aud", "attacker"),
        ("nonce", "wrong"),
        ("exp", time.time() - 60),
        ("email_verified", False),
    ]:
        with pytest.raises(ValueError):
            social.verify_identity(
                token({**claims, field: value}), "google", "client", "nonce", client
            )


def test_concurrent_budget_reservations_cannot_exceed_account_limit(hosted, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    info = register(TestClient(app))
    monkeypatch.setattr(hosted, "ai_account_daily_help", 1)

    def reserve_once():
        with SessionLocal() as db:
            account = db.query(Account).filter_by(email=info["email"]).one()
            try:
                hosted_ai.reserve(db, account, "help", "gpt-4.1-mini", 100, 256)
                return 200
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: reserve_once(), range(2)))
    assert sorted(results) == [200, 429]


def test_apple_form_post_requires_single_use_browser_state(hosted, monkeypatch):
    monkeypatch.setattr(hosted, "oauth_base_url", "https://testserver")
    monkeypatch.setattr(hosted, "oauth_apple_client_id", "synthetic-apple-client")
    monkeypatch.setattr(hosted, "oauth_apple_client_secret", "synthetic-apple-secret")
    client = TestClient(app, base_url="https://testserver")
    start = client.get("/api/oauth/apple/start", follow_redirects=False)
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["response_mode"] == ["form_post"]
    assert (
        "SameSite=none" in start.headers["set-cookie"] and "Secure" in start.headers["set-cookie"]
    )
    body = {"state": query["state"][0], "code": "synthetic-code"}
    origin = {"Origin": "https://appleid.apple.com"}
    path = "/api/oauth/apple/callback"
    assert (
        TestClient(app, base_url="https://testserver")
        .post(path, data=body, headers=origin)
        .status_code
        == 400
    )
    email = secrets.token_hex(8) + "@example.com"
    monkeypatch.setattr(social, "exchange", lambda *args: ("apple-" + email, email))
    assert client.post(path, data=body, headers=origin, follow_redirects=False).status_code == 303
    assert client.get("/api/account").json()["email"] == email
    assert client.post(path, data=body, headers=origin).status_code == 400
