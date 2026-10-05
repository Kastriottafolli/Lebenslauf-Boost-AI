"""Only the dedicated operator key powers this opt-in software help endpoint."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.database import get_db
from backend.services import boosty_service, session_service

router = APIRouter(tags=['Boosty assistant'])


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session_id: str = Field(..., max_length=36)
    question: str = Field(..., min_length=2, max_length=2000)
    language: str = Field('de', pattern='^(de|en|sq)$')
    consent: bool = False


@router.get('/api/assistant/config')
def config():
    return {'enabled': boosty_service.enabled(), 'provider':'openai', 'scope':'software-help'}


@router.post('/api/assistant')
def ask(req: Question, db=Depends(get_db), x_session_token: str = Header('')):
    session_service.get_session(db, req.session_id, x_session_token)
    if not req.consent:
        raise HTTPException(422, 'Datenübermittlung zuerst bestätigen / confirm data sharing')
    if not boosty_service.enabled():
        raise HTTPException(503, 'Boosty-KI noch nicht aktiviert. Lokale Hilfe ist verfügbar / local help available.')
    boosty_service.reserve(db, req.session_id)
    return boosty_service.answer(boosty_service.classify(req.question), req.language)
