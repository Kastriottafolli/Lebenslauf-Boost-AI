"""Sitzungen anlegen und laden."""

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from backend.models import Session


def create_session(db: DBSession, language: str) -> Session:
    sess = Session(language=language if language in ("de", "en") else "de")
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def get_session(db: DBSession, session_id: str) -> Session:
    sess = db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Sitzung nicht gefunden / session not found")
    return sess
