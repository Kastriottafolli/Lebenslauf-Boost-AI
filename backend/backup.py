"""Encrypted SQLite snapshots with verification and bounded local retention.

The backup encryption key stays outside the database and backup directories.
Verification never extracts files or overwrites a live database.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sqlite3
import stat
import tarfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

MAX_DATABASE_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
BACKUP_TIMEOUT_SECONDS = 120
BACKUP_NAME = re.compile(r"^tafolliboost-backup-(\d{8}T\d{12}Z)\.fernet$")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _private_file(path: Path, *, max_bytes: int = 512) -> bytes:
    if path.is_symlink():
        raise ValueError("Private files must not be symlinks.")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("Private files must be regular files with mode 0600.")
    if info.st_size > max_bytes:
        raise ValueError("Private file exceeds the permitted size.")
    return path.read_bytes()


def _private_directory(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError("The backup directory must not be a symlink.")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ValueError("The backup directory must have mode 0700.")
    return path.resolve()


def _encryption_key(path: Path, *excluded_directories: Path) -> Fernet:
    resolved = path.resolve()
    if any(resolved.is_relative_to(directory.resolve()) for directory in excluded_directories):
        raise ValueError("The encryption key must stay outside database and backup directories.")
    try:
        return Fernet(_private_file(path).strip())
    except ValueError as error:
        if "Private" in str(error):
            raise
        raise ValueError("The backup encryption key is invalid.") from None


def _database_checks(
    connection: sqlite3.Connection, admin_key: bytes | None, mail_key: bytes | None = None
) -> None:
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("SQLite integrity verification failed.")
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin_access'"
    ).fetchone()
    records = (
        connection.execute("SELECT secret_cipher FROM admin_access").fetchall() if exists else []
    )
    if records and not admin_key:
        raise ValueError("An admin encryption key is required for this database.")
    if admin_key:
        try:
            cipher = Fernet(admin_key.strip())
            for (encrypted_secret,) in records:
                cipher.decrypt(encrypted_secret.encode())
        except (ValueError, InvalidToken, TypeError, AttributeError):
            raise ValueError("The admin encryption key does not match the database.") from None

    mail_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='email_outbox'"
    ).fetchone()
    messages = (
        connection.execute(
            "SELECT payload_cipher FROM email_outbox WHERE payload_cipher IS NOT NULL"
        ).fetchall()
        if mail_exists
        else []
    )
    if messages and not mail_key:
        raise ValueError("A mail encryption key is required for pending messages.")
    if mail_key:
        try:
            mail_cipher = Fernet(mail_key.strip())
            for (encrypted_payload,) in messages:
                mail_cipher.decrypt(encrypted_payload.encode())
        except (ValueError, InvalidToken, TypeError, AttributeError):
            raise ValueError("The mail encryption key does not match the database.") from None


def _snapshot(database: Path, admin_key: bytes | None, mail_key: bytes | None = None) -> bytes:
    if database.is_symlink() or not database.is_file():
        raise ValueError("The SQLite database must be an existing regular file.")
    source_uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=10) as source:
        page_size = source.execute("PRAGMA page_size").fetchone()[0]
        pages = source.execute("PRAGMA page_count").fetchone()[0]
        if page_size * pages > MAX_DATABASE_BYTES:
            raise ValueError("Database exceeds the 256 MiB backup limit.")
        deadline = time.monotonic() + BACKUP_TIMEOUT_SECONDS

        def progress(_status, _remaining, total):
            if total * page_size > MAX_DATABASE_BYTES:
                raise ValueError("Database exceeds the 256 MiB backup limit.")
            if time.monotonic() > deadline:
                raise ValueError("SQLite snapshot timed out.")

        with sqlite3.connect(":memory:") as snapshot:
            source.backup(snapshot, pages=1024, progress=progress, sleep=0.1)
            _database_checks(snapshot, admin_key, mail_key)
            data = snapshot.serialize()
    if len(data) > MAX_DATABASE_BYTES:
        raise ValueError("Database exceeds the 256 MiB backup limit.")
    # The snapshot is complete and independent of the source WAL. These header
    # bytes select rollback-journal format for standalone restore/deserialization.
    if data[:16] != b"SQLite format 3\x00":
        raise ValueError("Snapshot is not a SQLite database.")
    return data[:18] + b"\x01\x01" + data[20:]


def _add_member(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(data)
    member.mode = 0o600
    archive.addfile(member, io.BytesIO(data))


def _bundle(
    snapshot: bytes, admin_key: bytes | None, created_at: datetime, mail_key: bytes | None = None
) -> bytes:
    metadata = {
        "format": 2,
        "created_at": created_at.isoformat(),
        "admin_key_included": admin_key is not None,
        "mail_key_included": mail_key is not None,
    }
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        _add_member(archive, "database.sqlite3", snapshot)
        _add_member(archive, "metadata.json", json.dumps(metadata).encode())
        if admin_key is not None:
            _add_member(archive, "admin-secrets.key", admin_key)
        if mail_key is not None:
            _add_member(archive, "mail-secrets.key", mail_key)
    return output.getvalue()


def _validate_bundle(data: bytes) -> dict:
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            allowed = {"database.sqlite3", "metadata.json", "admin-secrets.key", "mail-secrets.key"}
            limits = {
                "database.sqlite3": MAX_DATABASE_BYTES,
                "metadata.json": 4096,
                "admin-secrets.key": 512,
                "mail-secrets.key": 512,
            }
            contents = {}
            for member in archive:
                if member.name not in allowed or member.name in contents or not member.isfile():
                    raise ValueError("Unexpected backup archive contents.")
                if member.size <= 0 or member.size > limits[member.name]:
                    raise ValueError("Backup member exceeds the permitted size.")
                contents[member.name] = archive.extractfile(member).read()
            if not {"database.sqlite3", "metadata.json"}.issubset(contents):
                raise ValueError("Expected backup contents are missing.")
        metadata = json.loads(contents["metadata.json"])
        if (
            not isinstance(metadata, dict)
            or metadata.get("format") not in {1, 2}
            or type(metadata.get("admin_key_included")) is not bool
            or metadata["admin_key_included"] != ("admin-secrets.key" in contents)
        ):
            raise ValueError("Backup metadata is invalid.")
        if metadata["format"] == 2 and (
            type(metadata.get("mail_key_included")) is not bool
            or metadata["mail_key_included"] != ("mail-secrets.key" in contents)
        ):
            raise ValueError("Mail backup metadata is invalid.")
        if metadata["format"] == 1 and "mail-secrets.key" in contents:
            raise ValueError("Unexpected mail key in legacy backup.")
        try:
            created_at = datetime.fromisoformat(metadata["created_at"])
        except ValueError:
            raise ValueError("Backup timestamp is invalid.") from None
        if created_at.tzinfo is None:
            raise ValueError("Backup timestamp must include its timezone.")
        with sqlite3.connect(":memory:") as connection:
            connection.deserialize(contents["database.sqlite3"])
            _database_checks(
                connection, contents.get("admin-secrets.key"), contents.get("mail-secrets.key")
            )
        return metadata
    except (
        tarfile.TarError,
        sqlite3.Error,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
    ):
        raise ValueError("Backup verification failed.") from None


def cleanup_backups(directory: Path, retention_days: int = 14) -> int:
    if not 1 <= retention_days <= 365:
        raise ValueError("Retention must be between 1 and 365 days.")
    directory = _private_directory(directory)
    cutoff = _utcnow() - timedelta(days=retention_days)
    deleted = 0
    for path in directory.iterdir():
        match = BACKUP_NAME.fullmatch(path.name)
        if not match or path.is_symlink() or not path.is_file():
            continue
        try:
            created_at = datetime.strptime(match[1], "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)
        except ValueError:
            continue
        if created_at < cutoff:
            path.unlink()
            deleted += 1
    return deleted


def create_backup(
    database: Path,
    key_file: Path,
    directory: Path,
    *,
    admin_key_file: Path | None = None,
    mail_key_file: Path | None = None,
    retention_days: int = 14,
) -> Path:
    if not 1 <= retention_days <= 365:
        raise ValueError("Retention must be between 1 and 365 days.")
    directory = _private_directory(directory)
    cipher = _encryption_key(key_file, database.resolve().parent, directory)
    admin_key = _private_file(admin_key_file) if admin_key_file else None
    mail_key = _private_file(mail_key_file) if mail_key_file and mail_key_file.exists() else None
    created_at = _utcnow()
    bundle = _bundle(_snapshot(database, admin_key, mail_key), admin_key, created_at, mail_key)
    _validate_bundle(bundle)
    encrypted = cipher.encrypt(bundle)
    if len(encrypted) > MAX_ARCHIVE_BYTES:
        raise ValueError("Encrypted backup exceeds the permitted size.")
    destination = directory / f"tafolliboost-backup-{created_at:%Y%m%dT%H%M%S%fZ}.fernet"
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(encrypted)
            output.flush()
            os.fsync(output.fileno())
        verify_backup(destination, key_file)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    cleanup_backups(directory, retention_days)
    return destination


def verify_backup(archive: Path, key_file: Path) -> dict:
    cipher = _encryption_key(key_file, archive.resolve().parent)
    encrypted = _private_file(archive, max_bytes=MAX_ARCHIVE_BYTES)
    try:
        return _validate_bundle(cipher.decrypt(encrypted))
    except InvalidToken:
        raise ValueError("Backup authentication failed; incorrect key or damaged file.") from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create and verify an encrypted snapshot")
    create.add_argument("--database", type=Path, required=True)
    create.add_argument("--key-file", type=Path, required=True)
    create.add_argument("--directory", type=Path, required=True)
    create.add_argument("--admin-key", type=Path)
    create.add_argument("--mail-key", type=Path)
    create.add_argument("--retention-days", type=int, default=14)
    verify = commands.add_parser(
        "verify", help="Verify without extracting or modifying any database"
    )
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--key-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "create":
            destination = create_backup(
                args.database,
                args.key_file,
                args.directory,
                admin_key_file=args.admin_key,
                mail_key_file=args.mail_key,
                retention_days=args.retention_days,
            )
            print(f"Encrypted backup created and verified: {destination}")
        else:
            metadata = verify_backup(args.archive, args.key_file)
            print(
                f"Backup verified: SQLite integrity OK; admin key included: {metadata['admin_key_included']}; "
                f"mail key included: {metadata.get('mail_key_included', False)}"
            )
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
