import sqlite3

from sqlalchemy import create_engine

from backend.language_migration import migrate_session_languages


def test_expand_language_constraint_preserves_rows_children_and_indexes(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE sessions(id TEXT PRIMARY KEY, language VARCHAR(2) NOT NULL CHECK(language IN ('de','en')), owner_token_hash TEXT);
        CREATE INDEX owner_index ON sessions(owner_token_hash);
        CREATE TABLE documents(id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id));
        INSERT INTO sessions VALUES ('original','de','private-hash');
        INSERT INTO documents VALUES ('document','original');
        """)
    engine = create_engine("sqlite:///" + str(path))
    migrate_session_languages(engine)
    migrate_session_languages(engine)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO sessions VALUES ('new','sq','another-hash')")
        assert db.execute("SELECT session_id FROM documents").fetchall() == [("original",)]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT name FROM sqlite_master WHERE name='owner_index'").fetchone()
        assert (
            db.execute("SELECT owner_token_hash FROM sessions WHERE id='original'").fetchone()[0]
            == "private-hash"
        )
    backup = path.with_name(path.name + ".before-albanian.bak")
    assert backup.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(backup) as db:
        assert db.execute("SELECT id FROM sessions").fetchall() == [("original",)]
    engine.dispose()
