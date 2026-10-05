"""Password hashing, expiring login cookies and one-time recovery codes."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request

from backend.models import Account, Login
from backend.services.session_service import token_hash


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"{salt}:{digest}"


def password_matches(password, stored):
    return secrets.compare_digest(password_hash(password, stored.split(":")[0]), stored)


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
