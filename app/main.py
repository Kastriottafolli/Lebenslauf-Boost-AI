"""FastAPI-App — Lebenslauf Boost AI.

Endpoints:
  GET  /                 -> Frontend (SPA)
  GET  /api/status       -> Anbieter-/RAG-Status
  POST /api/session      -> neue Sitzung
  POST /api/upload-cv    -> Lebenslauf hochladen (RAG-Index aufbauen)
  POST /api/generate     -> Lebenslauf generieren (einzeln oder Vergleich)
  POST /api/refine       -> iteratives Verfeinern (Conversation History)
  POST /api/export       -> als PDF oder DOCX herunterladen
"""

import base64
import json
import os
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session as DBSession

from . import __version__, export, prompts, rag, schemas
from .config import get_settings
from .database import get_db, init_db
from .llm import service
from .models import CVDocument, Generation, Message, Session

settings = get_settings()

# Tabellen beim Import anlegen — robust, egal ob via uvicorn oder TestClient gestartet.
init_db()

app = FastAPI(title=settings.app_name, version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# ──────────────────────────────────────────────────────────────────────────
# Frontend
# ──────────────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


# ──────────────────────────────────────────────────────────────────────────
# Status
# ──────────────────────────────────────────────────────────────────────────
@app.get("/api/status", response_model=schemas.StatusOut)
def status():
    return schemas.StatusOut(
        app=settings.app_name,
        version=__version__,
        providers=service.provider_status(),
        rag_mode="embeddings" if settings.openai_enabled else "tfidf",
    )


# ──────────────────────────────────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────────────────────────────────
@app.post("/api/session", response_model=schemas.SessionOut)
def create_session(language: str = "de", db: DBSession = Depends(get_db)):
    sess = Session(language=language)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return schemas.SessionOut(session_id=sess.id, language=sess.language, has_cv=False)


def _get_session(db: DBSession, session_id: str) -> Session:
    sess = db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Sitzung nicht gefunden / session not found")
    return sess


# ──────────────────────────────────────────────────────────────────────────
# Upload-CV (RAG)
# ──────────────────────────────────────────────────────────────────────────
@app.post("/api/upload-cv", response_model=schemas.UploadOut)
async def upload_cv(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    openai_key: str = Form(""),
    db: DBSession = Depends(get_db),
):
    sess = _get_session(db, session_id)
    data = await file.read()

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"Datei zu groß (max. {settings.max_upload_mb} MB).")

    from .extract import extract_photo, extract_text

    try:
        text = extract_text(file.filename, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    index = rag.build_index(text, openai_key=openai_key)

    # Bewerbungsfoto aus dem CV extrahieren (falls vorhanden).
    photo_data_url = None
    try:
        photo_bytes = extract_photo(file.filename, data)
        if photo_bytes:
            photo_data_url = "data:image/jpeg;base64," + base64.b64encode(photo_bytes).decode()
    except Exception:
        photo_data_url = None

    # Vorhandenen CV ersetzen.
    if sess.cv:
        db.delete(sess.cv)
        db.flush()
    cv = CVDocument(
        session_id=sess.id,
        filename=file.filename,
        content=text,
        index_json=rag.dumps(index),
        photo_data_url=photo_data_url,
    )
    db.add(cv)
    db.commit()

    return schemas.UploadOut(
        session_id=sess.id,
        filename=file.filename,
        characters=len(text),
        chunks=len(index["chunks"]),
        rag_mode=rag.index_mode(index),
        preview=text[:400],
        photo=photo_data_url,
    )


# ──────────────────────────────────────────────────────────────────────────
# Generate (Single oder Compare)
# ──────────────────────────────────────────────────────────────────────────
@app.post("/api/generate", response_model=schemas.GenerateResponse)
def generate(req: schemas.GenerateRequest, db: DBSession = Depends(get_db)):
    sess = _get_session(db, req.session_id)
    sess.job_description = req.job_description
    sess.wishes = req.wishes or ""
    sess.language = req.language
    keys = req.keys.model_dump() if req.keys else {}

    # ── RAG: relevante Lebenslauf-Auszüge abrufen (Dynamic Context Injection) ──
    cv_full = sess.cv.content if sess.cv else ""
    cv_context = []
    if sess.cv:
        index = rag.loads(sess.cv.index_json)
        query = f"{req.job_description}\n{req.wishes or ''}"
        cv_context = rag.retrieve(index, query, openai_key=keys.get("openai"))

    system = prompts.system_prompt(req.language)
    user_msg = prompts.build_user_message(
        job_description=req.job_description,
        wishes=req.wishes or "",
        cv_context=cv_context,
        language=req.language,
        technique=req.technique,
    )
    demo_payload = {
        "cv_full": cv_full,
        "job_description": req.job_description,
        "wishes": req.wishes or "",
    }

    providers = (
        ["claude", "openai"] if req.provider == "compare" else [req.provider]
    )

    results = []
    for pname in providers:
        out = service.run_generation(
            pname, system, [{"role": "user", "content": user_msg}],
            language=req.language, demo_payload=demo_payload, keys=keys,
        )
        analysis = rag.analyze(req.job_description, out["content"])
        gen = Generation(
            session_id=sess.id,
            provider=out["provider"],
            model=out["model"],
            technique=req.technique,
            content=out["content"],
            ats_score=analysis["ats_score"],
            matched_keywords=json.dumps(analysis["matched_keywords"]),
            missing_keywords=json.dumps(analysis["missing_keywords"]),
        )
        db.add(gen)
        db.flush()
        results.append(
            schemas.GenerationOut(
                generation_id=gen.id,
                provider=out["provider"],
                model=out["model"],
                technique=req.technique,
                content=out["content"],
                analysis=schemas.KeywordAnalysis(**analysis),
                is_demo=out["is_demo"],
            )
        )

    # Conversation History: Prompt + (beste) Antwort speichern.
    db.add(Message(session_id=sess.id, role="user", content=user_msg))

    response = schemas.GenerateResponse(
        mode="compare" if req.provider == "compare" else "single",
        results=results,
    )
    if req.provider == "compare" and len(results) >= 2:
        rec = service.recommend([r.model_dump() for r in results], req.language)
        response.winner_provider = rec["winner_provider"]
        response.recommendation = rec["recommendation"]
        winner = next(r for r in results if r.provider == rec["winner_provider"])
        db.add(Message(session_id=sess.id, role="assistant", content=winner.content))
    else:
        db.add(Message(session_id=sess.id, role="assistant", content=results[0].content))

    db.commit()
    return response


# ──────────────────────────────────────────────────────────────────────────
# Refine (Conversation History)
# ──────────────────────────────────────────────────────────────────────────
@app.post("/api/refine", response_model=schemas.GenerationOut)
def refine(req: schemas.RefineRequest, db: DBSession = Depends(get_db)):
    sess = _get_session(db, req.session_id)

    history = (
        db.query(Message)
        .filter(Message.session_id == sess.id)
        .order_by(Message.created_at)
        .all()
    )
    last_user = next(
        (m.content for m in reversed(history) if m.role == "user"), ""
    )
    last_assistant = req.current_content or next(
        (m.content for m in reversed(history) if m.role == "assistant"), ""
    )
    if not last_user or not last_assistant:
        raise HTTPException(
            409, "Bitte zuerst einen Lebenslauf generieren / generate a CV first."
        )

    system = prompts.system_prompt(req.language)
    messages = [
        {"role": "user", "content": last_user},
        {"role": "assistant", "content": last_assistant},
        {"role": "user", "content": prompts.refine_message(req.instruction, req.language)},
    ]
    demo_payload = {
        "cv_full": sess.cv.content if sess.cv else last_assistant,
        "job_description": sess.job_description or "",
        "wishes": req.instruction,
    }

    keys = req.keys.model_dump() if req.keys else {}
    out = service.run_generation(
        req.provider, system, messages, language=req.language,
        demo_payload=demo_payload, keys=keys,
    )
    analysis = rag.analyze(sess.job_description or req.instruction, out["content"])

    gen = Generation(
        session_id=sess.id, provider=out["provider"], model=out["model"],
        technique="refine", content=out["content"], ats_score=analysis["ats_score"],
        matched_keywords=json.dumps(analysis["matched_keywords"]),
        missing_keywords=json.dumps(analysis["missing_keywords"]),
    )
    db.add(gen)
    db.add(Message(session_id=sess.id, role="user", content=req.instruction))
    db.add(Message(session_id=sess.id, role="assistant", content=out["content"]))
    db.flush()
    gen_id = gen.id
    db.commit()

    return schemas.GenerationOut(
        generation_id=gen_id,
        provider=out["provider"],
        model=out["model"],
        technique="refine",
        content=out["content"],
        analysis=schemas.KeywordAnalysis(**analysis),
        is_demo=out["is_demo"],
    )


# ──────────────────────────────────────────────────────────────────────────
# Export (PDF / DOCX)
# ──────────────────────────────────────────────────────────────────────────
@app.post("/api/export")
def export_cv(req: schemas.ExportRequest):
    safe_name = "".join(c for c in (req.filename or "Lebenslauf") if c.isalnum() or c in " _-").strip()
    safe_name = safe_name.replace(" ", "_") or "Lebenslauf"

    photo_bytes = _decode_photo(req.photo)

    if req.format == "docx":
        data = export.to_docx(req.content, req.design, req.language, photo=photo_bytes)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = "docx"
    elif req.format == "pdf":
        data = export.to_pdf(req.content, req.design, req.language, photo=photo_bytes)
        media = "application/pdf"
        ext = "pdf"
    else:
        raise HTTPException(422, "Format muss 'pdf' oder 'docx' sein.")

    filename = f"{safe_name}_{req.design}.{ext}"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _decode_photo(data_url: Optional[str]) -> Optional[bytes]:
    """Wandelt eine data-URL (data:image/...;base64,...) in Bytes um."""
    if not data_url or "," not in data_url:
        return None
    try:
        return base64.b64decode(data_url.split(",", 1)[1])
    except Exception:
        return None


# Statische Assets (CSS/JS) zuletzt mounten, damit /api Vorrang hat.
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
