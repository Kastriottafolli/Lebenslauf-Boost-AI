"""FastAPI-App-Fabrik — Lebenslauf Boost AI.

Diese Datei ist bewusst dünn: Sie erstellt nur die App, registriert die
Router (backend/routers/) und bindet Frontend + statische Dateien ein.
Die eigentliche Logik lebt in backend/services/ und backend/llm/.

Start:  uvicorn backend.main:app --reload   (oder: python run.py)
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

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
    from backend.cleanup import cleanup

    cleanup()

    @asynccontextmanager
    async def lifespan(_app):
        async def hourly_cleanup():
            while True:
                await asyncio.sleep(3600)
                try:
                    await asyncio.to_thread(cleanup)
                except Exception:
                    logging.getLogger(__name__).exception("Scheduled database cleanup failed")

        task = asyncio.create_task(hourly_cleanup())
        async def deliver_account_mail():
            from backend.services.account_mail import drain

            while True:
                try:
                    await asyncio.to_thread(drain)
                except Exception:
                    # Mail errors must never include payloads or SMTP credentials.
                    logging.getLogger(__name__).warning("Transactional mail worker unavailable")
                await asyncio.sleep(settings.mail_poll_seconds)

        mail_task = asyncio.create_task(deliver_account_mail())
        try:
            yield
        finally:
            task.cancel()
            mail_task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            with suppress(asyncio.CancelledError):
                await mail_task

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.secure_cookies else "/docs",
        redoc_url=None if settings.secure_cookies else "/redoc",
        openapi_url=None if settings.secure_cookies else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.security import install_security

    install_security(app)

    for router in ALL_ROUTERS:
        app.include_router(router)

    # Dateien zuletzt mounten, damit /api Vorrang hat:
    #   /assets -> frontend/ (CSS, JS)     /static -> static/ (Logo, Bilder)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


app = create_app()
