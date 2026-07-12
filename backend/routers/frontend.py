"""Frontend-Endpunkt: liefert die Single-Page-App aus dem Ordner frontend/."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["Frontend"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_DIR = PROJECT_ROOT / "static"


@router.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
