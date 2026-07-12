"""Status-Endpunkt: Welche KI-Anbieter sind aktiv, welcher RAG-Modus läuft?"""

from fastapi import APIRouter

from backend import __version__, schemas
from backend.config import get_settings
from backend.llm import llm_service

router = APIRouter(tags=["System"])
settings = get_settings()


@router.get("/api/status", response_model=schemas.StatusOut)
def status():
    return schemas.StatusOut(
        app=settings.app_name,
        version=__version__,
        providers=llm_service.provider_status(),
        rag_mode="embeddings" if settings.openai_enabled else "tfidf",
    )
