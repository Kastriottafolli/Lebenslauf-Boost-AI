"""Expand the SQLite language constraint without losing sessions or their children."""

import os
import re
from pathlib import Path


def migrate_session_languages(engine):
    if engine.dialect.name != "sqlite":
        return
    raw = engine.raw_connection()
    try:
        raw.commit()
        schema = raw.execute("SELECT sql FROM sqlite_master WHERE name='sessions'").fetchone()[0]
        if "'sq'" in schema:
            return
        expanded = re.sub(
            r"language\s+IN\s*\(\s*'de'\s*,\s*'en'\s*\)",
            "language IN ('de','en','sq')",
            schema,
            flags=re.I,
        )
        if expanded == schema:
            raise RuntimeError("Unknown sessions language constraint; migration aborted")
        database = engine.url.database
        if database and database != ":memory:":
            import sqlite3

            backup_path = Path(database + ".before-albanian.bak")
            if not backup_path.exists():
                descriptor = os.open(backup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                with sqlite3.connect(backup_path) as backup:
                    raw.driver_connection.backup(backup)
                backup_path.chmod(0o600)
        indexes = raw.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name='sessions' AND type IN ('index','trigger') AND sql IS NOT NULL"
        ).fetchall()
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("BEGIN IMMEDIATE")
        try:
            expanded = re.sub(
                r"CREATE TABLE\s+[\"`\[]?sessions[\"`\]]?",
                "CREATE TABLE sessions_languages_new",
                expanded,
                count=1,
                flags=re.I,
            )
            raw.execute(expanded)
            raw.execute("INSERT INTO sessions_languages_new SELECT * FROM sessions")
            raw.execute("DROP TABLE sessions")
            raw.execute("ALTER TABLE sessions_languages_new RENAME TO sessions")
            for (statement,) in indexes:
                raw.execute(statement)
            if raw.execute("PRAGMA foreign_key_check").fetchone():
                raise RuntimeError("Foreign key validation failed; migration rolled back")
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.execute("PRAGMA foreign_keys=ON")
    finally:
        raw.close()
