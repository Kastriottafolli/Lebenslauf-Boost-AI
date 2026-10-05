"""Session ownership; identifiers alone never grant access."""

import hashlib
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from backend.models import Session


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: DBSession, language: str, owner_id=None):
    token = secrets.token_urlsafe(32)
    sess = Session(
        language=language if language in ("de", "en") else "de",
        owner_token_hash=token_hash(token),
        owner_id=owner_id,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    sess.access_token = token
    return sess


def get_session(db: DBSession, session_id: str, token=""):
    sess = db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Sitzung nicht gefunden / session not found")
    if (
        not token
        or not sess.owner_token_hash
        or not secrets.compare_digest(sess.owner_token_hash, token_hash(token))
    ):
        raise HTTPException(403, "Kein Zugriff auf diese Sitzung / access denied")
    return sess
