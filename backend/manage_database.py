"""Initialize, inspect, or consistently back up the configured SQLite database."""

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import inspect, text

from backend.database import engine, init_db


def backup_database(directory: Path) -> Path:
    if engine.dialect.name != "sqlite" or engine.url.database in (None, "", ":memory:"):
        raise ValueError("This backup command requires a file-based SQLite database.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = directory / f"tafolli-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.db"
    # Exclusive creation: never overwrite an existing backup.
    with destination.open("xb"):
        pass
    destination.chmod(0o600)
    with engine.connect() as connection:
        source = connection.connection.driver_connection
        with sqlite3.connect(destination) as target:
            source.backup(target)
            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity check failed.")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "status", "backup"))
    parser.add_argument("--directory", type=Path, default=Path("data/backups"))
    args = parser.parse_args()
    init_db()
    if args.command == "backup":
        print(f"Verified backup: {backup_database(args.directory)}")
        return
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            if connection.execute(text("PRAGMA quick_check")).scalar_one() != "ok":
                raise RuntimeError("Database integrity check failed.")
        print("Tables:", ", ".join(sorted(inspect(engine).get_table_names())))
    print("Database initialized; no initial user password or account is created.")


if __name__ == "__main__":
    main()
