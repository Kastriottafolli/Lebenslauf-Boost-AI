"""Only the dedicated operator key powers this opt-in software help endpoint."""

import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.database import get_db
from backend.services import boosty_service, session_service

router = APIRouter(tags=["Boosty assistant"])


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(..., max_length=36)
    question: str = Field(..., min_length=2, max_length=2000)
    language: str = Field("de", pattern="^(de|en|sq)$")
    consent: bool = False


@router.get("/api/assistant/config")
def config():
    return {"enabled": boosty_service.enabled(), "provider": "openai", "scope": "software-help"}


@router.post("/api/assistant")
def ask(req: Question, request: Request, db=Depends(get_db), x_session_token: str = Header("")):
    sess = session_service.get_session(db, req.session_id, x_session_token)
    if not req.consent:
        raise HTTPException(422, "Datenübermittlung zuerst bestätigen / confirm data sharing")
    if re.search(
        r"(?:sk-|xai-|AIza)[a-zA-Z0-9_-]{20,}|(?:password|passwort|fjalëkalim)\s*[:=]\s*\S+|\b[0-9a-f]{32,64}\b",
        req.question,
        re.IGNORECASE,
    ):
        raise HTTPException(
            422, "Keine Zugangsdaten in den Chat eingeben / do not enter credentials in chat"
        )
    if not boosty_service.enabled():
        raise HTTPException(
            503,
            "Boosty-KI noch nicht aktiviert. Lokale Hilfe ist verfügbar / local help available.",
        )
    from backend.config import get_settings

    if get_settings().hosted_ai_enabled:
        import json

        from backend.services import hosted_ai

        account = hosted_ai.authenticated_session(db, request, sess)
        schema = {
            "type": "object",
            "properties": {"topic": {"type": "string", "enum": list(boosty_service.HELP)}},
            "required": ["topic"],
            "additionalProperties": False,
        }
        result = hosted_ai.Provider(db, account, "help").generate(
            boosty_service.SYSTEM, [{"role": "user", "content": req.question}], schema=schema
        )
        try:
            topic = json.loads(result.content)["topic"]
        except (ValueError, KeyError, TypeError):
            topic = "unknown"
        return boosty_service.answer(topic, req.language)
    boosty_service.reserve(db, req.session_id)
    return boosty_service.answer(boosty_service.classify(req.question), req.language)
