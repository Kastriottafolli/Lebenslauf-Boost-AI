"""Server-only OpenAI requests with persistent, conservative spending reservations."""

import math
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException
from sqlalchemy import text

from backend.config import get_settings
from backend.llm.base import LLMResult
from backend.llm.http_provider import response_text
from backend.models import AdminAccess, AIBudget, AICall
from backend.services.account_service import current_account


def authenticated_session(db, request, session):
    account = current_account(db, request, True)
    if db.get(AdminAccess, account.id):
        raise HTTPException(403, "Bitte ein normales Nutzerkonto verwenden / use a user account")
    if session.owner_id != account.id:
        raise HTTPException(
            403, "Sitzung gehört nicht zu deinem Konto / session ownership mismatch"
        )
    return account


def configured():
    return bool(get_settings().openai_api_key.strip())


def reserve(db, account, kind, model, input_bytes, max_output):
    s = get_settings()
    day = datetime.now(UTC).date().isoformat()
    # UTF-8 bytes bound token input conservatively; fixed overhead covers the schema.
    amount = math.ceil(
        (input_bytes + 2048) * s.ai_input_usd_per_million + max_output * s.ai_output_usd_per_million
    )
    db.commit()
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    try:
        query = db.query(AICall).filter(AICall.day == day)
        limit = {
            "package": s.ai_account_daily_packages,
            "refine": s.ai_account_daily_refines,
            "help": s.ai_account_daily_help,
        }[kind]
        if query.filter(AICall.account_id == account.id, AICall.kind == kind).count() >= limit:
            raise HTTPException(
                429,
                "Dein Tageslimit für diese KI-Funktion ist erreicht / daily feature limit reached",
            )
        budget = db.get(AIBudget, day)
        if budget is None:
            budget = AIBudget(
                day=day,
                calls=0,
                reserved_microusd=0,
                actual_microusd=0,
                input_tokens=0,
                output_tokens=0,
            )
            db.add(budget)
        if (
            budget.calls >= s.ai_global_daily_calls
            or budget.reserved_microusd + amount > s.ai_daily_budget_usd * 1_000_000
        ):
            raise HTTPException(
                429,
                "KI-Tageskontingent ausgeschöpft. Bitte später erneut versuchen / daily AI capacity reached",
            )
        budget.calls += 1
        budget.reserved_microusd += amount
        call = AICall(
            account_id=account.id, day=day, kind=kind, model=model, reserved_microusd=amount
        )
        db.add(call)
        db.commit()
        return call.id
    except Exception:
        db.rollback()
        raise


class Provider:
    def __init__(self, db, account, kind):
        self.db, self.account, self.kind = db, account, kind
        self.model = (
            get_settings().hosted_help_model
            if kind == "help"
            else get_settings().hosted_openai_model
        )

    def available(self):
        return configured()

    def generate(self, system, messages, schema=None):
        s = get_settings()
        if not configured():
            raise HTTPException(503, "KI derzeit nicht eingerichtet / AI currently unavailable")
        maximum = {"package": 10000, "refine": 4000, "help": 256}[self.kind]
        body = {
            "model": self.model,
            "input": [{"role": "system", "content": system}, *messages],
            "store": False,
            "max_output_tokens": maximum,
        }
        if schema:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "application" if self.kind == "package" else "help_topic",
                    "strict": True,
                    "schema": schema,
                }
            }
        if self.model.startswith(("gpt-5", "gpt-6")):
            body["reasoning"] = {"effort": "low"}
        call_id = reserve(
            self.db,
            self.account,
            self.kind,
            self.model,
            sum(len(m["content"].encode()) for m in body["input"]),
            maximum,
        )
        call = self.db.get(AICall, call_id)
        try:
            with httpx.Client(
                timeout=httpx.Timeout(120, connect=10), follow_redirects=False, trust_env=False
            ) as client:
                response = client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {s.openai_api_key}"},
                    json=body,
                )
            if response.status_code != 200:
                raise HTTPException(
                    502,
                    "OpenAI gerade nicht verfügbar. Bitte später erneut versuchen / AI currently unavailable",
                )
            data = response.json()
            usage = data.get("usage") or {}
            call.input_tokens = int(usage.get("input_tokens", 0))
            call.output_tokens = int(usage.get("output_tokens", 0))
            call.actual_microusd = math.ceil(
                call.input_tokens * s.ai_input_usd_per_million
                + call.output_tokens * s.ai_output_usd_per_million
            )
            content = response_text("openai", data)
            call.status = "success"
            return LLMResult(content, "openai", self.model)
        except HTTPException:
            call.status = "failed"
            raise
        except (httpx.HTTPError, ValueError, TypeError):
            call.status = "failed"
            raise HTTPException(502, "KI-Anfrage fehlgeschlagen / AI request failed") from None
        finally:
            # Failed/abandoned requests retain their reservation; no retry can bypass limits.
            if self.db.bind.dialect.name == "sqlite":
                self.db.commit()
                self.db.execute(text("BEGIN IMMEDIATE"))
            budget = self.db.get(AIBudget, call.day)
            budget.input_tokens += call.input_tokens
            budget.output_tokens += call.output_tokens
            budget.actual_microusd += call.actual_microusd
            self.db.commit()
