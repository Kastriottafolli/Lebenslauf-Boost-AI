"""SQLite-Datenbank-Setup (SQLAlchemy)."""

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import get_settings

settings = get_settings()

# Sicherstellen, dass die Datenverzeichnisse existieren.
os.makedirs("data", exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},  # nötig für SQLite + FastAPI
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

    # Add ownership without exposing existing sessions. Old rows are intentionally unclaimed.
    columns = {c["name"] for c in inspect(engine).get_columns("sessions")}
    with engine.begin() as connection:
        for name in ("owner_token_hash", "owner_id"):
            if name not in columns:
                connection.execute(text(f"ALTER TABLE sessions ADD COLUMN {name} VARCHAR(64)"))
        # Preserve historic generations in the old table; safely copy once into expanded schema.
        if "generations" in inspect(engine).get_table_names():
            connection.execute(
                text(
                    "INSERT INTO generations_v2 SELECT * FROM generations WHERE id NOT IN (SELECT id FROM generations_v2)"
                )
            )
