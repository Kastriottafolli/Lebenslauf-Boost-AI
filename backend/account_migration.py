"""Idempotent, additive profile expansion; never rebuild or replace account rows."""

from sqlalchemy import inspect, text

PROFILE_COLUMNS = {
    "gender": "VARCHAR(16) NOT NULL DEFAULT 'undisclosed'",
    "date_of_birth": "VARCHAR(10)",
    "street": "VARCHAR(300) NOT NULL DEFAULT ''",
    "postal_code": "VARCHAR(32) NOT NULL DEFAULT ''",
    "city": "VARCHAR(200) NOT NULL DEFAULT ''",
    "country": "VARCHAR(2) NOT NULL DEFAULT ''",
    "spoken_languages": "TEXT NOT NULL DEFAULT '[]'",
}


def migrate_account_profiles(engine):
    inspector = inspect(engine)
    if "account_profiles" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("account_profiles")}
    with engine.begin() as connection:
        for name, definition in PROFILE_COLUMNS.items():
            if name not in columns:
                # Identifiers and definitions come only from the fixed schema above.
                connection.execute(text(f"ALTER TABLE account_profiles ADD COLUMN {name} {definition}"))
