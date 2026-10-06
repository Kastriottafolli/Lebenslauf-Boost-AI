"""Encrypted snapshots must preserve SQLite/WAL and the matching admin key."""

import io
import sqlite3
import stat
import subprocess
import sys
import tarfile
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from backend import backup


def private_key(path, value=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value or Fernet.generate_key())
    path.chmod(0o600)
    return path


@pytest.fixture
def sources(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    database = state / "app.db"
    key = private_key(tmp_path / "keys" / "backup.key")
    admin_key = private_key(state / "admin-secrets.key")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE applicants (email TEXT)")
        connection.execute("INSERT INTO applicants VALUES ('synthetic@example.test')")
        connection.execute("CREATE TABLE admin_access (secret_cipher TEXT)")
        secret = Fernet(admin_key.read_bytes()).encrypt(b"synthetic-admin-secret").decode()
        connection.execute("INSERT INTO admin_access VALUES (?)", (secret,))
    return database, key, admin_key, tmp_path / "encrypted"


def decrypted_contents(archive, key):
    plaintext = Fernet(key.read_bytes()).decrypt(archive.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as bundle:
        return {member.name: bundle.extractfile(member).read() for member in bundle}


def test_wal_roundtrip_and_recovery_preserve_admin_authentication(sources, tmp_path):
    database, key, admin_key, directory = sources
    # Keep the source open so committed data remains in the WAL during backup.
    with sqlite3.connect(database) as source:
        source.execute("INSERT INTO applicants VALUES ('wal@example.test')")
        source.commit()
        archive = backup.create_backup(database, key, directory, admin_key_file=admin_key)
        source.execute("INSERT INTO applicants VALUES ('after-backup@example.test')")
        source.commit()
        assert source.execute("SELECT count(*) FROM applicants").fetchone()[0] == 3
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert b"synthetic@example.test" not in archive.read_bytes()
    assert admin_key.read_bytes() not in archive.read_bytes()
    assert backup.verify_backup(archive, key)["admin_key_included"] is True
    contents = decrypted_contents(archive, key)
    assert set(contents) == {"database.sqlite3", "metadata.json", "admin-secrets.key"}
    recovered = tmp_path / "restored.db"
    recovered.write_bytes(contents["database.sqlite3"])
    recovered.chmod(0o600)
    with sqlite3.connect(recovered) as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT email FROM applicants ORDER BY email").fetchall() == [
            ("synthetic@example.test",),
            ("wal@example.test",),
        ]
        encrypted_secret = connection.execute("SELECT secret_cipher FROM admin_access").fetchone()[
            0
        ]
    assert (
        Fernet(contents["admin-secrets.key"]).decrypt(encrypted_secret.encode())
        == b"synthetic-admin-secret"
    )


def test_snapshot_remains_transactionally_consistent_during_writes(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    database = state / "app.db"
    key = private_key(tmp_path / "keys" / "backup.key")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE state (value INTEGER)")
        connection.execute("INSERT INTO state VALUES (0)")
        connection.execute("CREATE TABLE events (value INTEGER)")
    started = threading.Event()
    errors = []

    def writer():
        try:
            with sqlite3.connect(database) as connection:
                for index in range(1, 30):
                    connection.execute("UPDATE state SET value=?", (index,))
                    connection.execute("INSERT INTO events VALUES (?)", (index,))
                    connection.commit()
                    started.set()
                    time.sleep(0.001)
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        assert started.wait(2)
        archive = backup.create_backup(database, key, tmp_path / "encrypted")
    finally:
        thread.join(5)
    assert not thread.is_alive() and not errors
    contents = decrypted_contents(archive, key)
    with sqlite3.connect(":memory:") as connection:
        connection.deserialize(contents["database.sqlite3"])
        assert (
            connection.execute("SELECT value FROM state").fetchone()[0]
            == connection.execute("SELECT count(*) FROM events").fetchone()[0]
        )


def test_active_wal_database_can_be_backed_up_with_read_only_source_permissions(sources):
    database, key, admin_key, directory = sources
    with sqlite3.connect(database) as writer:
        writer.execute("INSERT INTO applicants VALUES ('readonly-wal@example.test')")
        writer.commit()
        wal = database.with_name(database.name + "-wal")
        shared_memory = database.with_name(database.name + "-shm")
        assert wal.exists() and shared_memory.exists()
        original_modes = {
            path: stat.S_IMODE(path.stat().st_mode) for path in (database, wal, shared_memory)
        }
        try:
            database.parent.chmod(0o500)
            for path in original_modes:
                path.chmod(0o400)
            archive = backup.create_backup(database, key, directory, admin_key_file=admin_key)
        finally:
            database.parent.chmod(0o700)
            for path, mode in original_modes.items():
                path.chmod(mode)
    contents = decrypted_contents(archive, key)
    with sqlite3.connect(":memory:") as restored:
        restored.deserialize(contents["database.sqlite3"])
        assert (
            restored.execute(
                "SELECT count(*) FROM applicants WHERE email='readonly-wal@example.test'"
            ).fetchone()[0]
            == 1
        )


def test_admin_key_is_required_and_must_match(sources, tmp_path):
    database, key, admin_key, directory = sources
    with pytest.raises(ValueError, match="admin encryption key is required"):
        backup.create_backup(database, key, directory)
    incorrect = private_key(tmp_path / "keys" / "incorrect-admin.key")
    with pytest.raises(ValueError, match="does not match"):
        backup.create_backup(database, key, directory, admin_key_file=incorrect)
    assert not list(directory.iterdir())
    admin_key.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        backup.create_backup(database, key, directory, admin_key_file=admin_key)


def test_private_permissions_and_key_separation_are_enforced(sources):
    database, key, admin_key, directory = sources
    key.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        backup.create_backup(database, key, directory, admin_key_file=admin_key)
    key.chmod(0o600)
    misplaced = private_key(database.parent / "backup.key")
    with pytest.raises(ValueError, match="outside"):
        backup.create_backup(database, misplaced, directory, admin_key_file=admin_key)
    misplaced = private_key(directory / "backup.key")
    directory.chmod(0o700)
    with pytest.raises(ValueError, match="outside"):
        backup.create_backup(database, misplaced, directory, admin_key_file=admin_key)


def test_corruption_wrong_key_and_cli_verification_do_not_change_live_database(sources, tmp_path):
    database, key, admin_key, directory = sources
    archive = backup.create_backup(database, key, directory, admin_key_file=admin_key)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.backup",
            "verify",
            "--archive",
            str(archive),
            "--key-file",
            str(key),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "SQLite integrity OK" in result.stdout
    assert key.read_text() not in result.stdout + result.stderr
    live_before = database.read_bytes()
    wrong_key = private_key(tmp_path / "keys" / "wrong.key")
    with pytest.raises(ValueError, match="authentication failed"):
        backup.verify_backup(archive, wrong_key)
    corrupted = bytearray(archive.read_bytes())
    corrupted[len(corrupted) // 2] ^= 1
    archive.write_bytes(corrupted)
    with pytest.raises(ValueError, match="authentication failed"):
        backup.verify_backup(archive, key)
    assert database.read_bytes() == live_before


def test_existing_archive_is_never_overwritten(sources, monkeypatch):
    database, key, admin_key, directory = sources
    fixed = datetime(2026, 10, 5, tzinfo=UTC)
    monkeypatch.setattr(backup, "_utcnow", lambda: fixed)
    archive = backup.create_backup(database, key, directory, admin_key_file=admin_key)
    before = archive.read_bytes()
    with pytest.raises(FileExistsError):
        backup.create_backup(database, key, directory, admin_key_file=admin_key)
    assert archive.read_bytes() == before


def test_retention_removes_only_old_owned_backup_names(tmp_path, monkeypatch):
    directory = tmp_path / "encrypted"
    directory.mkdir(mode=0o700)
    now = datetime(2026, 10, 5, tzinfo=UTC)
    monkeypatch.setattr(backup, "_utcnow", lambda: now)
    old_name = f"tafolliboost-backup-{now - timedelta(days=15):%Y%m%dT%H%M%S%fZ}.fernet"
    boundary = f"tafolliboost-backup-{now - timedelta(days=14):%Y%m%dT%H%M%S%fZ}.fernet"
    old = directory / old_name
    old.write_bytes(b"old fixture")
    (directory / boundary).write_bytes(b"keep boundary")
    for name in ["other.fernet", "manual.db", "tafolliboost-backup-20261305T000000000000Z.fernet"]:
        (directory / name).write_bytes(b"keep unrelated")
    target = tmp_path / "unrelated"
    target.write_bytes(b"keep symlink target")
    symlink = directory / f"tafolliboost-backup-{now - timedelta(days=20):%Y%m%dT%H%M%S%fZ}.fernet"
    symlink.symlink_to(target)
    assert backup.cleanup_backups(directory) == 1
    assert not old.exists()
    assert (directory / boundary).exists() and symlink.is_symlink() and target.exists()
    assert len(list(directory.iterdir())) == 5


def test_authenticated_archive_with_symlink_or_oversized_member_is_rejected(sources, monkeypatch):
    database, key, admin_key, directory = sources
    archive = backup.create_backup(database, key, directory, admin_key_file=admin_key)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        member = tarfile.TarInfo("database.sqlite3")
        member.type = tarfile.SYMTYPE
        member.linkname = str(database)
        bundle.addfile(member)
    archive.write_bytes(Fernet(key.read_bytes()).encrypt(output.getvalue()))
    with pytest.raises(ValueError, match="Unexpected"):
        backup.verify_backup(archive, key)
    archive.unlink()
    archive = backup.create_backup(database, key, directory, admin_key_file=admin_key)
    monkeypatch.setattr(backup, "MAX_DATABASE_BYTES", 1)
    with pytest.raises(ValueError, match="member exceeds"):
        backup.verify_backup(archive, key)


def test_missing_database_is_not_created_and_invalid_retention_preserves_files(tmp_path):
    database = tmp_path / "state" / "missing.db"
    database.parent.mkdir()
    key = private_key(tmp_path / "keys" / "backup.key")
    directory = tmp_path / "encrypted"
    with pytest.raises(ValueError, match="existing regular"):
        backup.create_backup(database, key, directory)
    assert not database.exists()
    with pytest.raises(ValueError, match="Retention"):
        backup.create_backup(database, key, directory, retention_days=0)
    assert not list(directory.iterdir())


def test_pending_mail_requires_matching_key_and_is_recoverable(sources, tmp_path):
    database, key, admin_key, directory = sources
    mail_key = private_key(database.parent / "mail-secrets.key")
    ciphertext = (
        Fernet(mail_key.read_bytes()).encrypt(b'{"token":"synthetic-one-time-link"}').decode()
    )
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE email_outbox (payload_cipher TEXT)")
        connection.execute("INSERT INTO email_outbox VALUES (?)", (ciphertext,))
    with pytest.raises(ValueError, match="mail encryption key is required"):
        backup.create_backup(database, key, directory, admin_key_file=admin_key)
    wrong = private_key(tmp_path / "keys" / "wrong-mail.key")
    with pytest.raises(ValueError, match="mail encryption key does not match"):
        backup.create_backup(
            database, key, directory, admin_key_file=admin_key, mail_key_file=wrong
        )
    archive = backup.create_backup(
        database, key, directory, admin_key_file=admin_key, mail_key_file=mail_key
    )
    contents = decrypted_contents(archive, key)
    assert backup.verify_backup(archive, key)["mail_key_included"] is True
    assert b"synthetic-one-time-link" not in archive.read_bytes()
    with sqlite3.connect(":memory:") as connection:
        connection.deserialize(contents["database.sqlite3"])
        encrypted = connection.execute("SELECT payload_cipher FROM email_outbox").fetchone()[0]
    assert (
        Fernet(contents["mail-secrets.key"]).decrypt(encrypted.encode())
        == b'{"token":"synthetic-one-time-link"}'
    )


def test_legacy_format_one_backup_remains_verifiable(sources):
    import json

    database, key, admin_key, directory = sources
    archive = backup.create_backup(database, key, directory, admin_key_file=admin_key)
    contents = decrypted_contents(archive, key)
    metadata = json.loads(contents["metadata.json"])
    metadata["format"] = 1
    metadata.pop("mail_key_included")
    contents["metadata.json"] = json.dumps(metadata).encode()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        for name, content in contents.items():
            backup._add_member(bundle, name, content)
    archive.write_bytes(Fernet(key.read_bytes()).encrypt(output.getvalue()))
    assert backup.verify_backup(archive, key)["format"] == 1
