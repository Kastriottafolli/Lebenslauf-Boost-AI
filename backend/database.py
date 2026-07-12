"""SQLite-Datenbank-Setup (SQLAlchemy)."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import get_settings

settings = get_settings()

# Sicherstellen, dass die Datenverzeichnisse existieren.
os.makedirs("data", exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # nötig für SQLite + FastAPI
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """FastAPI-Dependency: liefert eine DB-Session und schließt sie sauber."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend import models  # noqa: F401  (Modelle registrieren)

    Base.metadata.create_all(bind=engine)
