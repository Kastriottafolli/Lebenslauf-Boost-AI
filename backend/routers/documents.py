"""Upload-Endpunkt: Lebenslauf hochladen und für RAG indexieren."""

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession
from starlette.concurrency import run_in_threadpool

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
    x_session_token: str = Header(""),
):
    sess = session_service.get_session(db, session_id, x_session_token)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    chunks, size = [], 0
    while chunk := await file.read(65536):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(413, "Datei zu groß / file too large")
        chunks.append(chunk)
    data = b"".join(chunks)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"Datei zu groß (max. {settings.max_upload_mb} MB).")

    try:
        result = await run_in_threadpool(
            document_service.store_cv,
            db,
            sess,
            filename=file.filename,
            data=data,
            openai_key=openai_key,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    return schemas.UploadOut(session_id=sess.id, **result)
