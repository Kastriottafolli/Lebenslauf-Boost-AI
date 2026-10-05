"""Explicit CLI provisioning, encrypted TOTP, replay prevention and short admin sessions."""

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import update

from backend.config import get_settings
from backend.models import Account, AdminAccess, AdminAudit, AdminLogin, Login
from backend.services.account_service import password_hash
from backend.services.session_service import token_hash


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def cipher(create=False):
    path = Path(get_settings().admin_key_file)
    if create and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as output:
                output.write(Fernet.generate_key())
    if not path.exists():
        raise HTTPException(503, "Admin-Schlüssel fehlt / admin key unavailable")
    return Fernet(path.read_bytes().strip())


def totp(secret, counter):
    digest = hmac.new(base64.b32decode(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{value:06d}"


def accept_totp(db, access, code):
    secret = cipher().decrypt(access.secret_cipher.encode()).decode()
    counter = int(time.time()) // 30
    for candidate in (counter, counter - 1, counter + 1):
        if candidate > access.last_counter and secrets.compare_digest(
            totp(secret, candidate), code
        ):
            changed = db.execute(
                update(AdminAccess)
                .where(
                    AdminAccess.account_id == access.account_id,
                    AdminAccess.last_counter < candidate,
                )
                .values(last_counter=candidate)
            ).rowcount
            if changed:
                return True
    return False


def provision(db, email, directory, reset_existing=False):
    email = email.strip().lower()
    # Never promote a self-registered account: require server owner to resolve it explicitly.
    account = db.query(Account).filter_by(email=email).first()
    existing_access = db.get(AdminAccess, account.id) if account else None
    if account and (not reset_existing or not existing_access):
        raise ValueError(
            "E-Mail bereits belegt. Keine automatische Rechtevergabe an ein bestehendes Konto."
        )
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    token = secrets.token_urlsafe(32)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = directory / f"admin-setup-{secrets.token_hex(6)}.txt"
    if not account:
        account = Account(email=email)
        db.add(account)
    account.password_hash = password_hash(secrets.token_urlsafe(64))
    account.recovery_hash = token_hash(secrets.token_urlsafe(64))
    db.flush()
    access = existing_access or AdminAccess(account_id=account.id)
    access.enabled = False
    access.secret_cipher = cipher(True).encrypt(secret.encode()).decode()
    access.last_counter = -1
    access.setup_hash = token_hash(token)
    access.setup_expires_at = now() + timedelta(hours=24)
    db.add(access)
    if existing_access:
        db.query(AdminLogin).filter_by(account_id=account.id).delete()
        db.query(Login).filter_by(account_id=account.id).delete()
        db.add(AdminAudit(admin_id=account.id, action="admin.cli.reset"))
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(
            f"Boosty AI – private Admin-Einrichtung\nE-Mail: {email}\nEinrichtungscode: {token}\n\nÖffne /admin und wähle Ersteinrichtung. Gib E-Mail und Einrichtungscode ein.\nLege dein eigenes Passwort fest und verbinde deine Authenticator-App.\nDer Code ist einmalig und läuft nach 24 Stunden ab. Nicht teilen.\n"
        )
    db.commit()
    return destination


def current_admin(db, request):
    authorization = request.headers.get("Authorization", "")
    token = (
        authorization[7:]
        if authorization.startswith("Bearer ")
        else request.cookies.get("boosty_admin", "")
    )
    login = db.get(AdminLogin, token_hash(token)) if token else None
    if not login or login.expires_at <= now():
        raise HTTPException(
            401, "Admin-Anmeldung mit Zwei-Faktor-Code erforderlich / admin sign-in required"
        )
    access = db.get(AdminAccess, login.account_id)
    if not access or not access.enabled:
        raise HTTPException(403, "Keine Admin-Berechtigung / admin access denied")
    return db.get(Account, login.account_id)


def issue_login(db, account, response):
    token = secrets.token_urlsafe(32)
    db.add(
        AdminLogin(
            token_hash=token_hash(token),
            account_id=account.id,
            expires_at=now() + timedelta(minutes=15),
        )
    )
    db.commit()
    response.set_cookie(
        "boosty_admin",
        token,
        max_age=900,
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="strict",
        path="/",
    )
    return {"email": account.email, "access_token": token, "expires_in": 900}


def audit(db, admin, action, subject=None):
    db.add(AdminAudit(admin_id=admin.id if admin else None, action=action, subject_id=subject))
    db.commit()
