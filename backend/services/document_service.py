"""Lebenslauf-Upload: Text/Foto extrahieren und RAG-Index aufbauen."""

import base64

from sqlalchemy.orm import Session as DBSession

from backend.models import CVDocument, Session
from backend.services import extraction_service, rag_service, safe_extraction


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
    text, photo_data_url = safe_extraction.extract(filename, data)
    index = {"chunks": rag_service.chunk_text(text), "embeddings": None}

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
        "source_text": text,
        "profile": {},
        "photo": photo_data_url,
    }


def _extract_photo_data_url(filename: str, data: bytes) -> str | None:
    try:
        photo_bytes = extraction_service.extract_photo(filename, data)
        if photo_bytes:
            return "data:image/jpeg;base64," + base64.b64encode(photo_bytes).decode()
    except Exception:
        pass
    return None
