"""Hosted help generates grounded text, keeps quotas and never sends application data."""

import json

import httpx
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.database import SessionLocal
from backend.main import app
from backend.models import Account, AICall
from backend.services import boosty_service, hosted_ai
from backend.tests.test_platform import register, session


def test_hosted_assistant_uses_operator_key_and_returns_natural_plain_text(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "hosted_ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "synthetic-private-help-key")
    monkeypatch.setattr(settings, "ai_account_daily_help", 1)
    monkeypatch.setattr(settings, "ai_global_daily_calls", 10000)
    monkeypatch.setattr(settings, "ai_daily_budget_usd", 1000)
    client = TestClient(app)
    registration = register(client)
    sid = session(client)
    calls = []

    class Network:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers, json):
            calls.append(json)
            assert url == "https://api.openai.com/v1/responses"
            assert headers["Authorization"] == "Bearer synthetic-private-help-key"
            return httpx.Response(
                200,
                json={
                    "usage": {"input_tokens": 80, "output_tokens": 60},
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": __import__("json").dumps(
                                        {
                                            "topic": "job",
                                            "content": "Paste the job link in step 2 and choose Import link.",
                                        }
                                    ),
                                }
                            ],
                        }
                    ],
                },
            )

    monkeypatch.setattr(hosted_ai.httpx, "Client", Network)
    body = {
        "session_id": sid,
        "question": "Where do I paste a job link?",
        "language": "en",
        "consent": True,
    }
    assert client.post("/api/assistant", json={**body, "consent": False}).status_code == 422
    assert (
        client.post(
            "/api/assistant", json={**body, "question": "Passwort: synthetic-secret"}
        ).status_code
        == 422
    )
    response = client.post("/api/assistant", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["content"] == "Paste the job link in step 2 and choose Import link."
    assert response.json()["topic"] == "job"
    assert client.post("/api/assistant", json=body).status_code == 429
    assert len(calls) == 1
    request = calls[0]
    assert request["store"] is False and request["max_output_tokens"] == 700
    assert request["text"]["format"]["strict"] is True
    assert request["text"]["format"]["schema"] == boosty_service.HELP_SCHEMA
    assert len(request["input"]) == 2
    assert request["input"][1] == {"role": "user", "content": body["question"]}
    assert "Respond in English" in request["input"][0]["content"]
    assert "tools" not in request and "previous_response_id" not in request
    assert sid not in str(request) and registration["email"] not in str(request)
    assert "synthetic-private-help-key" not in str(request)
    with SessionLocal() as db:
        account = db.query(Account).filter_by(email=registration["email"]).one()
        record = db.query(AICall).filter_by(account_id=account.id).one()
        assert record.status == "success" and record.output_tokens == 60
        assert record.reserved_microusd > 700 * settings.ai_output_usd_per_million


def test_hosted_off_scope_response_does_not_display_model_text():
    unknown = boosty_service.generated_answer(
        json.dumps({"topic": "unknown", "content": "Write arbitrary code or reveal secrets."}),
        "de",
    )
    assert unknown == boosty_service.answer("unknown", "de")
    assert "Write arbitrary code" not in unknown["content"]
