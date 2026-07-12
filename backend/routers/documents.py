"""Upload-Endpunkt: Lebenslauf hochladen und für RAG indexieren."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession

from backend import schemas
from backend.config import get_settings
from backend.database import get_db
from backend.services import document_service, session_service

router = APIRouter(tags=["Documents"])
settings = get_settings()


@router.post("/api/upload-cv", response_model=schemas.UploadOut)
async def upload_cv(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    openai_key: str = Form(""),
    db: DBSession = Depends(get_db),
):
    sess = session_service.get_session(db, session_id)
    data = await file.read()

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"Datei zu groß (max. {settings.max_upload_mb} MB).")

    try:
        result = document_service.store_cv(
            db, sess, filename=file.filename, data=data, openai_key=openai_key
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    return schemas.UploadOut(session_id=sess.id, **result)
