"""Sitzungs-Endpunkt: neue Nutzersitzung anlegen."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DBSession

from backend import schemas
from backend.database import get_db
from backend.services import account_service, session_service

router = APIRouter(tags=["Sessions"])


@router.post("/api/session", response_model=schemas.SessionOut)
def create_session(request: Request, language: str = "de", db: DBSession = Depends(get_db)):
    account = account_service.current_account(db, request)
    sess = session_service.create_session(db, language, account.id if account else None)
    return schemas.SessionOut(
        session_id=sess.id,
        session_token=sess.access_token,
        language=sess.language,
        has_cv=False,
    )
