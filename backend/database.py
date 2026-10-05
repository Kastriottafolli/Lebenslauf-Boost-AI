"""SQLite-Datenbank-Setup (SQLAlchemy)."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import get_settings

settings = get_settings()

# Sicherstellen, dass die Datenverzeichnisse existieren.
os.makedirs("data", exist_ok=True)
os.makedirs(settings.upload_dir, exist_ok=True)
database_path = make_url(settings.database_url).database
if settings.database_url.startswith("sqlite") and database_path not in (None, "", ":memory:"):
    Path(database_path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},  # nötig für SQLite + FastAPI
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def sqlite_options(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


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
    if engine.dialect.name == "sqlite" and database_path not in (None, "", ":memory:"):
        Path(database_path).chmod(0o600)
    from backend.language_migration import migrate_session_languages

    migrate_session_languages(engine)
