"""Sitzungs-Endpunkt: neue Nutzersitzung anlegen."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from backend import schemas
from backend.database import get_db
from backend.services import session_service

router = APIRouter(tags=["Sessions"])


@router.post("/api/session", response_model=schemas.SessionOut)
def create_session(language: str = "de", db: DBSession = Depends(get_db)):
    sess = session_service.create_session(db, language)
    return schemas.SessionOut(session_id=sess.id, language=sess.language, has_cv=False)
