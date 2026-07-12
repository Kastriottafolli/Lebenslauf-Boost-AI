"""Lebenslauf-Upload: Text/Foto extrahieren und RAG-Index aufbauen."""

import base64
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from backend.models import CVDocument, Session
from backend.services import extraction_service, rag_service


def store_cv(
    db: DBSession,
    sess: Session,
    *,
    filename: str,
    data: bytes,
    openai_key: str = "",
) -> dict:
    """Extrahiert Text + Foto, baut den RAG-Index und ersetzt einen alten CV.

    Wirft ValueError bei nicht lesbaren/nicht unterstützten Dateien.
    """
    text = extraction_service.extract_text(filename, data)
    index = rag_service.build_index(text, openai_key=openai_key)
    photo_data_url = _extract_photo_data_url(filename, data)

    # Vorhandenen CV ersetzen (1:1-Beziehung pro Sitzung).
    if sess.cv:
        db.delete(sess.cv)
        db.flush()
    cv = CVDocument(
        session_id=sess.id,
        filename=filename,
        content=text,
        index_json=rag_service.dumps(index),
        photo_data_url=photo_data_url,
    )
    db.add(cv)
    db.commit()

    return {
        "filename": filename,
        "characters": len(text),
        "chunks": len(index["chunks"]),
        "rag_mode": rag_service.index_mode(index),
        "preview": text[:400],
        "photo": photo_data_url,
    }


def _extract_photo_data_url(filename: str, data: bytes) -> Optional[str]:
    try:
        photo_bytes = extraction_service.extract_photo(filename, data)
        if photo_bytes:
            return "data:image/jpeg;base64," + base64.b64encode(photo_bytes).decode()
    except Exception:
        pass
    return None
