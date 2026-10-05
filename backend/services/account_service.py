"""Password hashing, expiring login cookies and one-time recovery codes."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request

from backend.models import Account, Login
from backend.services.session_service import token_hash


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64 * 1024 * 1024
    ).hex()
    return f"scrypt$32768$8$3${salt}${digest}"


def password_matches(password, stored):
    try:
        if stored.startswith("scrypt$32768$8$3$"):
            return secrets.compare_digest(password_hash(password, stored.split("$")[4]), stored)
        salt, digest = stored.split(":")
        # Legacy hashes remain usable; the next successful login upgrades them.
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        return secrets.compare_digest(actual, digest)
    except (ValueError, IndexError):
        return False


DUMMY_HASH = password_hash("unavailable-password")


def limit_identity(db, email, category="user"):
    """Persistent per-identity limit supplements the HTTP per-client rate limit."""
    from sqlalchemy import text

    from backend.models import AuthAttempt

    bucket = token_hash(category + ":" + email.strip().lower())
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=15)
    # SQLite serializes writers: prevent parallel requests from racing the count.
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    db.query(AuthAttempt).filter(AuthAttempt.created_at < cutoff).delete()
    if db.query(AuthAttempt).filter(AuthAttempt.bucket == bucket).count() >= 10:
        db.rollback()
        raise HTTPException(
            429, "Zu viele Anmeldeversuche. Bitte 15 Minuten warten / wait 15 minutes"
        )
    db.add(AuthAttempt(bucket=bucket))
    db.commit()


def current_account(db, request: Request, required=False):
    auth = request.headers.get("Authorization", "")
    token = (
        auth.removeprefix("Bearer ")
        if auth.startswith("Bearer ")
        else request.cookies.get("candidaro_login", "")
    )
    login = db.get(Login, token_hash(token)) if token else None
    if login and login.expires_at > datetime.now(UTC).replace(tzinfo=None):
        account = db.get(Account, login.account_id)
        if account:
            return account
    if required:
        raise HTTPException(401, "Bitte anmelden / sign in first")
    return None


def login_cookie(db, account, response):
    from backend.config import get_settings

    token = secrets.token_urlsafe(32)
    db.add(
        Login(
            token_hash=token_hash(token),
            account_id=account.id,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=7),
        )
    )
    db.commit()
    response.set_cookie(
        "candidaro_login",
        token,
        max_age=7 * 86400,
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="lax",
        path="/",
    )
    return token
