"""FastAPI-App-Fabrik — Lebenslauf Boost AI.

Diese Datei ist bewusst dünn: Sie erstellt nur die App, registriert die
Router (backend/routers/) und bindet Frontend + statische Dateien ein.
Die eigentliche Logik lebt in backend/services/ und backend/llm/.

Start:  uvicorn backend.main:app --reload   (oder: python run.py)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.config import get_settings
from backend.database import init_db
from backend.routers import ALL_ROUTERS
from backend.routers.frontend import FRONTEND_DIR, STATIC_DIR


def create_app() -> FastAPI:
    settings = get_settings()

    # Tabellen beim Start anlegen — robust, egal ob via uvicorn oder TestClient.
    init_db()

    app = FastAPI(title=settings.app_name, version=__version__)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in ALL_ROUTERS:
        app.include_router(router)

    # Dateien zuletzt mounten, damit /api Vorrang hat:
    #   /assets -> frontend/ (CSS, JS)     /static -> static/ (Logo, Bilder)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


app = create_app()
