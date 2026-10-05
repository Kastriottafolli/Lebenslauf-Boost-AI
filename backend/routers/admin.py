"""Protected read-only administration. Secrets and arbitrary SQL never leave the server."""

import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, update

from backend.database import engine, get_db
from backend.models import (
    Account,
    Activity,
    AdminAccess,
    AdminAudit,
    AdminLogin,
    Application,
    AuthAttempt,
    CVDocument,
    DailyMetric,
    Generation,
    Login,
    Message,
    Session,
)
from backend.routers.platform import Credentials
from backend.services import admin_service as admins
from backend.services.account_service import (
    DUMMY_HASH,
    limit_identity,
    password_hash,
    password_matches,
)
from backend.services.session_service import token_hash

router = APIRouter(prefix="/api/admin", tags=["Administration"])


def protected(request: Request, db=Depends(get_db)):
    return admins.current_admin(db, request)


class SetupRequest(BaseModel):
    email: str = Field(..., max_length=254)
    setup_code: str = Field(..., min_length=30, max_length=100)


def pending(db, req):
    account = db.query(Account).filter_by(email=req.email.strip().lower()).first()
    access = db.get(AdminAccess, account.id) if account else None
    if (
        not access
        or access.enabled
        or not access.setup_hash
        or access.setup_expires_at <= admins.now()
        or not secrets.compare_digest(access.setup_hash, token_hash(req.setup_code))
    ):
        raise HTTPException(
            401, "Einrichtungscode ungültig oder abgelaufen / setup code invalid or expired"
        )
    return account, access


@router.post("/setup/begin")
def begin(req: SetupRequest, db=Depends(get_db)):
    limit_identity(db, req.email, "setup")
    _account, access = pending(db, req)
    return {
        "secret": admins.cipher().decrypt(access.secret_cipher.encode()).decode(),
        "issuer": "Boosty AI",
    }


class SetupFinish(SetupRequest):
    password: str = Field(..., min_length=14, max_length=128)
    code: str = Field(..., pattern=r"^\d{6}$")


@router.post("/setup/finish")
def finish(req: SetupFinish, response: Response, db=Depends(get_db)):
    limit_identity(db, req.email, "setup")
    account, access = pending(db, req)
    if not admins.accept_totp(db, access, req.code):
        raise HTTPException(
            401, "Authenticator-Code ungültig oder bereits verwendet / invalid or reused code"
        )
    changed = db.execute(
        update(AdminAccess)
        .where(
            AdminAccess.account_id == account.id,
            AdminAccess.enabled.is_(False),
            AdminAccess.setup_hash == token_hash(req.setup_code),
        )
        .values(enabled=True, setup_hash=None, setup_expires_at=None)
    ).rowcount
    if not changed:
        db.rollback()
        raise HTTPException(401, "Einrichtungscode bereits verwendet / setup code already used")
    account.password_hash = password_hash(req.password)
    db.query(Login).filter_by(account_id=account.id).delete()
    admins.audit(db, account, "admin.setup")
    return admins.issue_login(db, account, response)


class AdminCredentials(Credentials):
    code: str = Field(..., pattern=r"^\d{6}$")


@router.post("/login")
def login(req: AdminCredentials, response: Response, db=Depends(get_db)):
    limit_identity(db, req.email, "admin")
    account = db.query(Account).filter_by(email=req.normalized_email()).first()
    access = db.get(AdminAccess, account.id) if account else None
    stored = account.password_hash if account else DUMMY_HASH
    valid_password = password_matches(req.password, stored)
    if (
        not valid_password
        or not access
        or not access.enabled
        or not admins.accept_totp(db, access, req.code)
    ):
        admins.audit(db, None, "admin.login.denied")
        raise HTTPException(401, "Admin-Anmeldedaten ungültig / invalid admin credentials")
    admins.audit(db, account, "admin.login")
    return admins.issue_login(db, account, response)


@router.post("/logout")
def logout(request: Request, response: Response, admin=Depends(protected), db=Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else request.cookies.get("boosty_admin", "")
    db.query(AdminLogin).filter_by(token_hash=token_hash(token)).delete()
    admins.audit(db, admin, "admin.logout")
    response.delete_cookie("boosty_admin", path="/")
    return {"ok": True}


@router.get("/me")
def me(admin=Depends(protected)):
    return {"email": admin.email}


@router.get("/overview")
def overview(days: int = Query(30, ge=1, le=90), admin=Depends(protected), db=Depends(get_db)):
    cutoff = admins.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=days - 1
    )
    metrics = (
        db.query(DailyMetric)
        .filter(DailyMetric.day >= cutoff.date().isoformat())
        .order_by(DailyMetric.day)
        .all()
    )
    registrations = dict(
        db.query(func.date(Account.created_at), func.count(Account.id))
        .filter(Account.created_at >= cutoff)
        .group_by(func.date(Account.created_at))
        .all()
    )
    activity = (
        db.query(Activity.event, func.count(Activity.id))
        .filter(Activity.created_at >= cutoff, Activity.outcome < 400)
        .group_by(Activity.event)
        .all()
    )
    admins.audit(db, admin, "overview.read")
    return {
        "days": days,
        "totals": {
            "accounts": db.query(Account).count(),
            "new_accounts": sum(registrations.values()),
            "applications": db.query(Application).count(),
            "page_views": sum(m.page_views for m in metrics),
            "visit_sessions": sum(m.visits for m in metrics),
            "active_accounts": db.query(func.count(func.distinct(Activity.account_id)))
            .filter(Activity.created_at >= cutoff, Activity.outcome < 400)
            .scalar(),
        },
        "daily": [
            {
                "day": day,
                "page_views": next((m.page_views for m in metrics if m.day == day), 0),
                "visit_sessions": next((m.visits for m in metrics if m.day == day), 0),
                "registrations": registrations.get(day, 0),
            }
            for day in sorted(set(registrations) | {m.day for m in metrics})
        ],
        "operations": [{"event": event, "count": count} for event, count in activity],
        "measurement": "Seitenaufrufe und gestartete App-Sitzungen; keine eindeutigen Menschen. Bots, Reloads und Vorschau zählen mit. Keine IP-Adressen oder Werbe-Tracker.",
    }


@router.get("/users")
def users(
    q: str = Query("", max_length=254),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    admin=Depends(protected),
    db=Depends(get_db),
):
    query = db.query(Account)
    if q:
        query = query.filter(Account.email.contains(q.strip().lower(), autoescape=True))
    total = query.count()
    rows = query.order_by(Account.created_at.desc(), Account.id).offset(offset).limit(limit).all()
    ids = [row.id for row in rows]
    usage = dict(
        db.query(Activity.account_id, func.max(Activity.created_at))
        .filter(Activity.account_id.in_(ids))
        .group_by(Activity.account_id)
        .all()
    )
    projects = dict(
        db.query(Session.owner_id, func.count(Application.id))
        .join(Application, Application.session_id == Session.id)
        .filter(Session.owner_id.in_(ids))
        .group_by(Session.owner_id)
        .all()
    )
    admins.audit(db, admin, "users.read")
    return {
        "total": total,
        "offset": offset,
        "items": [
            {
                "id": row.id,
                "email": row.email,
                "created_at": row.created_at.isoformat(),
                "last_active_at": usage[row.id].isoformat() if row.id in usage else None,
                "applications": projects.get(row.id, 0),
            }
            for row in rows
        ],
    }


@router.get("/users/{account_id}")
def user_details(account_id: str, admin=Depends(protected), db=Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Konto nicht gefunden")
    sessions = (
        db.query(Session)
        .filter_by(owner_id=account.id)
        .order_by(Session.created_at.desc())
        .limit(100)
        .all()
    )
    projects = (
        db.query(Application)
        .join(Session, Application.session_id == Session.id)
        .filter(Session.owner_id == account.id)
        .order_by(Application.updated_at.desc())
        .limit(100)
        .all()
    )
    admins.audit(db, admin, "user.details.read", account.id)
    return {
        "id": account.id,
        "email": account.email,
        "created_at": account.created_at.isoformat(),
        "sessions": [
            {"id": s.id, "language": s.language, "created_at": s.created_at.isoformat()}
            for s in sessions
        ],
        "applications": [
            {
                "id": p.id,
                "title": p.title,
                "status": p.status,
                "updated_at": p.updated_at.isoformat(),
            }
            for p in projects
        ],
    }


@router.get("/applications/{project_id}")
def application(project_id: str, admin=Depends(protected), db=Depends(get_db)):
    project = db.get(Application, project_id)
    if not project:
        raise HTTPException(404, "Bewerbung nicht gefunden")
    admins.audit(db, admin, "application.content.read", project_id)
    return {"id": project.id, "data": json.loads(project.data_json)}


@router.get("/sessions/{session_id}")
def session_content(session_id: str, admin=Depends(protected), db=Depends(get_db)):
    sess = db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Sitzung nicht gefunden")
    admins.audit(db, admin, "session.content.read", session_id)
    cv = sess.cv
    return {
        "id": sess.id,
        "owner_id": sess.owner_id,
        "job_description": sess.job_description,
        "wishes": sess.wishes,
        "cv": {"filename": cv.filename, "content": cv.content} if cv else None,
        "generations": [
            {
                "id": g.id,
                "provider": g.provider,
                "model": g.model,
                "content": g.content,
                "created_at": g.created_at.isoformat(),
            }
            for g in db.query(Generation)
            .filter_by(session_id=sess.id)
            .order_by(Generation.created_at)
            .limit(100)
        ],
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in db.query(Message)
            .filter_by(session_id=sess.id)
            .order_by(Message.created_at)
            .limit(100)
        ],
    }


@router.get("/sessions")
def sessions(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    admin=Depends(protected),
    db=Depends(get_db),
):
    query = db.query(Session).order_by(Session.created_at.desc(), Session.id)
    admins.audit(db, admin, "sessions.read")
    return {
        "total": query.count(),
        "items": [
            {
                "id": s.id,
                "owner_id": s.owner_id,
                "created_at": s.created_at.isoformat(),
                "language": s.language,
            }
            for s in query.offset(offset).limit(limit)
        ],
    }


@router.get("/events")
def events(
    account_id: str = Query("", max_length=36),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin=Depends(protected),
    db=Depends(get_db),
):
    query = db.query(Activity, Account.email).outerjoin(Account, Activity.account_id == Account.id)
    if account_id:
        query = query.filter(Activity.account_id == account_id)
    admins.audit(db, admin, "events.read", account_id or None)
    return {
        "total": query.count(),
        "items": [
            {
                "id": e.id,
                "email": email,
                "event": e.event,
                "outcome": e.outcome,
                "created_at": e.created_at.isoformat(),
            }
            for e, email in query.order_by(Activity.created_at.desc(), Activity.id)
            .offset(offset)
            .limit(limit)
        ],
    }


@router.get("/audit")
def audit_log(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin=Depends(protected),
    db=Depends(get_db),
):
    admins.audit(db, admin, "audit.read")
    query = db.query(AdminAudit, Account.email).outerjoin(
        Account, AdminAudit.admin_id == Account.id
    )
    return {
        "total": query.count(),
        "items": [
            {
                "id": row.id,
                "email": email,
                "action": row.action,
                "subject_id": row.subject_id,
                "created_at": row.created_at.isoformat(),
            }
            for row, email in query.order_by(AdminAudit.created_at.desc(), AdminAudit.id)
            .offset(offset)
            .limit(limit)
        ],
    }


@router.get("/database")
def database(admin=Depends(protected), db=Depends(get_db)):
    models = [
        Account,
        Session,
        CVDocument,
        Generation,
        Message,
        Application,
        AuthAttempt,
        Login,
        AdminAccess,
        AdminLogin,
        Activity,
        DailyMetric,
        AdminAudit,
    ]
    admins.audit(db, admin, "database.read")
    return {
        "engine": engine.dialect.name,
        "tables": [
            {"name": model.__tablename__, "rows": db.query(model).count()} for model in models
        ],
        "integrity": "ok"
        if engine.dialect.name == "sqlite"
        and db.connection().exec_driver_sql("PRAGMA quick_check").scalar() == "ok"
        else "not_checked",
        "note": "Geschützte Datenansichten. Passwort-Hashes, Schlüssel und Tokens werden nicht angezeigt. Vollständige Sicherung nur per Server-CLI; kein SQL-Editor im Browser.",
    }
