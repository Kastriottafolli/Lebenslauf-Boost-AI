"""Verified accounts, versioned consent, passwords and expiring login cookies."""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import insert, select, text

from backend.models import Account, AdminAccess, Login
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


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def migrate_existing_accounts(engine):
    from backend.account_migration import migrate_account_profiles
    from backend.account_models import AccountProfile, AccountSecurity

    migrate_account_profiles(engine)
    with engine.begin() as connection:
        missing = select(Account.id).where(
            ~select(AccountSecurity.account_id)
            .where(AccountSecurity.account_id == Account.id)
            .exists()
        )
        for account_id in connection.execute(missing).scalars().all():
            connection.execute(insert(AccountSecurity).values(
                account_id=account_id, verified_at=now(), verification_source="legacy_existing",
                credential_version=1,
            ))
        # Security and profile gaps are independent: preserve any existing profile
        # and fill missing profiles for pending accounts without verifying them.
        missing_profiles = select(Account.id).where(
            ~select(AccountProfile.account_id)
            .where(AccountProfile.account_id == Account.id)
            .exists()
        )
        for account_id in connection.execute(missing_profiles).scalars().all():
            connection.execute(insert(AccountProfile).values(account_id=account_id))


def security_for(db, account):
    from backend.account_models import AccountSecurity

    security = db.get(AccountSecurity, account.id)
    if not security or not security.verified_at:
        raise HTTPException(403, {
            "code": "EMAIL_VERIFICATION_REQUIRED",
            "message": "Bitte bestätige zuerst deine E-Mail-Adresse. Du kannst eine neue Bestätigungs-E-Mail anfordern.",
        })
    return security


def normal_account(db, request):
    account = current_account(db, request, True)
    if db.get(AdminAccess, account.id):
        raise HTTPException(403, "Admin-Zugang separat verwenden")
    return account


def require_password(db, account, password):
    limit_identity(db, account.email, "sensitive")
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    # A request may have loaded this account before another password reset.
    # Recheck the current hash while holding the same lock as token consumption.
    db.refresh(account)
    if db.get(AdminAccess, account.id) or not password_matches(password, account.password_hash):
        raise HTTPException(401, {
            "code": "CURRENT_PASSWORD_INVALID", "message": "Aktuelles Passwort ist nicht korrekt.",
        })


def revoke_credentials(db, account):
    from backend.account_models import AccountActionToken, AccountSecurity, EmailOutbox

    security = db.get(AccountSecurity, account.id)
    security.credential_version += 1
    db.query(Login).filter_by(account_id=account.id).delete()
    db.query(AccountActionToken).filter_by(account_id=account.id).delete()
    db.query(EmailOutbox).filter(
        EmailOutbox.account_id == account.id,
        # Only links depend on the credential version. Contract/withdrawal
        # receipts and security notices must retain their delivery guarantees.
        EmailOutbox.purpose.in_(["verify", "reset", "change_email"]),
        EmailOutbox.status.in_(["pending", "sending"]),
    ).update({"status": "failed", "payload_cipher": None, "lease_until": None})


def action_token(db, account, purpose, target_email, language):
    from backend.account_models import AccountActionToken, AccountSecurity, EmailOutbox
    from backend.services import account_mail

    security = db.get(AccountSecurity, account.id)
    # An explicit resend invalidates previous links and unsent obsolete messages.
    db.query(AccountActionToken).filter_by(account_id=account.id, purpose=purpose).delete()
    db.query(EmailOutbox).filter(
        EmailOutbox.account_id == account.id, EmailOutbox.purpose == purpose,
        EmailOutbox.status.in_(["pending", "sending"]),
    ).update({"status": "failed", "payload_cipher": None, "lease_until": None})
    token = secrets.token_urlsafe(32)
    expiry = now() + (timedelta(minutes=30) if purpose == "reset" else timedelta(hours=24))
    db.add(AccountActionToken(
        token_hash=token_hash(token), account_id=account.id, purpose=purpose,
        target_email=target_email, credential_version=security.credential_version,
        expires_at=expiry,
    ))
    account_mail.queue(db, account, target_email, purpose, token, language, expiry)


def consume_token(db, token, purposes):
    from backend.account_models import AccountActionToken, AccountSecurity

    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    action = db.get(AccountActionToken, token_hash(token))
    security = db.get(AccountSecurity, action.account_id) if action else None
    account = db.get(Account, action.account_id) if action else None
    if security:
        db.refresh(security)
    if account:
        db.refresh(account)
    if (
        not action or action.purpose not in purposes or action.consumed_at
        or action.expires_at <= now() or not account or not security
        or action.credential_version != security.credential_version
        or db.get(AdminAccess, account.id)
    ):
        db.rollback()
        raise HTTPException(400, {
            "code": "ACCOUNT_LINK_INVALID",
            "message": "Dieser Link ist ungültig, bereits verwendet oder abgelaufen. Bitte einen neuen Link anfordern.",
        })
    action.consumed_at = now()
    return account, security, action


def profile_fields_json(profile):
    """Serialize only public profile fields; JSON storage stays an implementation detail."""
    from backend.profile_schema import PROFILE_FIELDS, AccountProfileFields

    defaults = AccountProfileFields().model_dump(mode="json")
    values = {
        name: getattr(profile, name, defaults[name]) if profile else defaults[name]
        for name in PROFILE_FIELDS
    }
    try:
        languages = json.loads(values["spoken_languages"]) if isinstance(values["spoken_languages"], str) else values["spoken_languages"]
    except (ValueError, TypeError):
        languages = []
    values["spoken_languages"] = languages if isinstance(languages, list) else []
    return values | {
        "preferences": {"email_notifications": bool(profile and profile.email_notifications)},
        "updated_at": profile.updated_at.isoformat() + "Z" if profile and profile.updated_at else None,
    }


def apply_profile_fields(profile, values):
    """Write validated allowlisted values, including JSON languages and optional date."""
    from backend.profile_schema import PROFILE_FIELDS

    for field, value in values.items():
        if field == "preferences":
            if "email_notifications" in value:
                profile.email_notifications = value["email_notifications"]
        elif field in PROFILE_FIELDS:
            if field == "spoken_languages":
                value = json.dumps(value, ensure_ascii=False)
            elif field == "date_of_birth" and value:
                value = value.isoformat() if hasattr(value, "isoformat") else value
            setattr(profile, field, value)


def profile_json(db, account):
    from backend.account_models import AccountProfile, AccountSecurity
    from backend.account_terms import PRIVACY_VERSION, TERMS_VERSION

    profile = db.get(AccountProfile, account.id)
    security = db.get(AccountSecurity, account.id)
    return {
        "email": account.email,
        "verified": bool(security and security.verified_at),
        "created_at": account.created_at.isoformat() + "Z",
        "profile": profile_fields_json(profile),
        "terms": {
            "version": TERMS_VERSION,
            "privacy_version": PRIVACY_VERSION,
            "accepted_version": security.terms_version if security else None,
            "current": bool(security and security.terms_version == TERMS_VERSION and security.privacy_version == PRIVACY_VERSION),
        },
    }


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
        if account and not db.get(AdminAccess, account.id):
            from backend.account_models import AccountSecurity

            security = db.get(AccountSecurity, account.id)
            if not security or not security.verified_at:
                if required:
                    security_for(db, account)
                return None
            return account
    if required:
        raise HTTPException(401, "Bitte anmelden / sign in first")
    return None


def login_cookie(db, account, response):
    from backend.config import get_settings

    security_for(db, account)
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
