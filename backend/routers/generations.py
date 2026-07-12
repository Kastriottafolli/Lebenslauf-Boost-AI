"""Generierungs-Endpunkte: erstellen (einzeln/Vergleich) und verfeinern."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from backend import schemas
from backend.database import get_db
from backend.services import generation_service, session_service

router = APIRouter(tags=["Generations"])


@router.post("/api/generate", response_model=schemas.GenerateResponse)
def generate(req: schemas.GenerateRequest, db: DBSession = Depends(get_db)):
    sess = session_service.get_session(db, req.session_id)
    return generation_service.generate(db, sess, req)


@router.post("/api/refine", response_model=schemas.GenerationOut)
def refine(req: schemas.RefineRequest, db: DBSession = Depends(get_db)):
    sess = session_service.get_session(db, req.session_id)
    return generation_service.refine(db, sess, req)
