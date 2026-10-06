"""Guarded support actions: validated profiles and ordinary expiring reset mail."""

import json
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError

from backend.account_models import AccountProfile, AccountSecurity
from backend.models import Account, AdminAccess, AdminAudit
from backend.profile_schema import AdminPasswordResetRequest, AdminProfilePatch
from backend.services import account_mail
from backend.services import account_service as accounts

RESERVED_ADMIN_EMAILS = frozenset({"info@tafolli.net"})


def _reserved(account):
    return account.email.strip().lower() in RESERVED_ADMIN_EMAILS


def _actor(db, admin):
    access = db.get(AdminAccess, admin.id) if admin else None
    if access:
        db.refresh(access)
    if not access or not access.enabled:
        raise HTTPException(403, {"code": "ADMIN_REQUIRED", "message": "Admin-Berechtigung erforderlich."})


def _target(db, account_id):
    account = db.query(Account).filter_by(id=account_id).with_for_update().populate_existing().first()
    if not account:
        raise HTTPException(404, {"code": "ACCOUNT_NOT_FOUND", "message": "Konto nicht gefunden."})
    if db.get(AdminAccess, account.id) or _reserved(account):
        raise HTTPException(403, {
            "code": "ADMIN_ACCOUNT_PROTECTED", "message": "Adminkonten können nicht über den Support geändert werden.",
        })
    return account


def user_details(db, account):
    """Safe detail fields that can be merged into the existing admin response."""
    profile = db.get(AccountProfile, account.id)
    security = db.get(AccountSecurity, account.id)
    is_admin, reserved = bool(db.get(AdminAccess, account.id)), _reserved(account)
    editable = not is_admin and not reserved
    fields = accounts.profile_fields_json(profile)
    return {
        "profile": fields,
        "profile_updated_at": fields["updated_at"],
        "is_admin": is_admin,
        "reserved_admin": reserved,
        "profile_editable": editable,
        "password_reset_allowed": bool(editable and security and security.verified_at),
    }


def _conflict(profile):
    raise HTTPException(409, {
        "code": "PROFILE_CONFLICT",
        "message": "Das Profil wurde inzwischen geändert. Bitte die aktuellen Daten prüfen.",
        "profile_updated_at": accounts.profile_fields_json(profile)["updated_at"],
    })


def _audit(db, admin, account, action, reason, changed_fields=()):
    db.add(AdminAudit(
        admin_id=admin.id, subject_id=account.id, action=action,
        reason=reason, changed_fields_json=json.dumps(sorted(changed_fields)),
    ))


def update_profile(db, admin, account_id, req: AdminProfilePatch):
    """Commit one allowlisted edit and its reason together, only at the expected version."""
    try:
        if db.bind.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        _actor(db, admin)
        account = _target(db, account_id)
        profile = db.query(AccountProfile).filter_by(account_id=account.id).populate_existing().first()
        if (profile.updated_at if profile else None) != req.expected_updated_at:
            _conflict(profile)
        values = req.profile.model_dump(exclude_unset=True)
        candidate = AccountProfile(account_id=account.id)
        accounts.apply_profile_fields(candidate, values)
        changed = {}
        for field in values:
            if field == "preferences":
                if "email_notifications" in values[field]:
                    changed["email_notifications"] = candidate.email_notifications
            else:
                changed[field] = getattr(candidate, field)
        timestamp = accounts.now()
        if profile and timestamp <= profile.updated_at:
            timestamp = profile.updated_at + timedelta(microseconds=1)
        changed["updated_at"] = timestamp
        if profile:
            applied = db.execute(
                update(AccountProfile).where(
                    AccountProfile.account_id == account.id,
                    AccountProfile.updated_at == req.expected_updated_at,
                ).values(**changed).execution_options(synchronize_session=False)
            ).rowcount
            if applied != 1:
                db.refresh(profile)
                _conflict(profile)
        else:
            candidate.updated_at = timestamp
            db.add(candidate)
        field_names = {name for name in changed if name != "updated_at"}
        if "email_notifications" in field_names:
            field_names.remove("email_notifications")
            field_names.add("preferences.email_notifications")
        _audit(db, admin, account, "user.profile.updated", req.reason, field_names)
        db.commit()
        db.expire_all()
        return user_details(db, account)
    except IntegrityError:
        db.rollback()
        _conflict(db.get(AccountProfile, account_id))
    except Exception:
        db.rollback()
        raise


def request_password_reset(db, admin, account_id, req: AdminPasswordResetRequest):
    """Queue the normal 30-minute single-use link; credentials remain unchanged."""
    try:
        if db.bind.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        _actor(db, admin)
        account = _target(db, account_id)
        security = db.get(AccountSecurity, account.id)
        if not security or not security.verified_at:
            raise HTTPException(409, {
                "code": "EMAIL_VERIFICATION_REQUIRED", "message": "Die E-Mail-Adresse muss zuerst bestätigt werden.",
            })
        account_mail.ensure_ready()
        profile = db.get(AccountProfile, account.id)
        accounts.action_token(db, account, "reset", account.email, profile.language if profile else "de")
        _audit(db, admin, account, "user.password_reset.requested", req.reason)
        db.commit()
        return {"ok": True, "status": "reset_email_queued"}
    except Exception:
        db.rollback()
        raise
