"""Protected administration with audited support edits and bounded reporting."""

import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, update

from backend.account_models import AccountProfile, AccountSecurity, EmailOutbox
from backend.config import get_settings
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
from backend.profile_schema import AdminPasswordResetRequest, AdminProfilePatch
from backend.routers.platform import Credentials
from backend.services import admin_service as admins
from backend.services.account_service import (
    DUMMY_HASH,
    limit_identity,
    password_hash,
    password_matches,
)
from backend.services.admin_application import ApplicationPatch
from backend.services.admin_dates import date_range
from backend.services.session_service import token_hash

router = APIRouter(prefix="/api/admin", tags=["Administration"])


def protected(request: Request, db=Depends(get_db)):
    return admins.current_admin(db, request)


@router.get("/auth-options")
def auth_options():
    return {"requires_totp": get_settings().admin_require_totp}


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
    if not get_settings().admin_require_totp:
        return {"requires_totp": False}
    return {
        "requires_totp": True,
        "secret": admins.cipher().decrypt(access.secret_cipher.encode()).decode(),
        "issuer": "Boosty AI",
    }


class SetupFinish(SetupRequest):
    password: str = Field(..., min_length=14, max_length=128)
    code: str | None = Field(None, pattern=r"^\d{6}$")


@router.post("/setup/finish")
def finish(req: SetupFinish, response: Response, db=Depends(get_db)):
    limit_identity(db, req.email, "setup")
    account, access = pending(db, req)
    if get_settings().admin_require_totp and (
        not req.code or not admins.accept_totp(db, access, req.code)
    ):
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
    code: str | None = Field(None, pattern=r"^\d{6}$")


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
        or (
            get_settings().admin_require_totp
            and (not req.code or not admins.accept_totp(db, access, req.code))
        )
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


def customer_accounts(db):
    return db.query(Account).filter(
        Account.email != get_settings().operator_email.strip().lower(),
        ~db.query(AdminAccess.account_id).filter(AdminAccess.account_id == Account.id).exists(),
    )


@router.get("/overview")
def overview(
    days: int = Query(30, ge=1, le=90),
    start: str | None = Query(None, max_length=10),
    end: str | None = Query(None, max_length=10),
    admin=Depends(protected), db=Depends(get_db),
):
    cutoff, until, period = date_range(admins.now(), days, start, end)
    metrics = db.query(DailyMetric).filter(
        DailyMetric.day >= period['start'], DailyMetric.day <= period['end'],
    ).order_by(DailyMetric.day).all()
    registrations = dict(customer_accounts(db).with_entities(func.date(Account.created_at), func.count(Account.id)).filter(
        Account.created_at >= cutoff, Account.created_at < until,
    ).group_by(func.date(Account.created_at)).all())
    activity = db.query(Activity.event, func.count(Activity.id)).filter(
        Activity.created_at >= cutoff, Activity.created_at < until, Activity.outcome < 400,
    ).group_by(Activity.event).all()
    from backend.models import AIBudget
    ai = db.query(AIBudget).filter(AIBudget.day >= period['start'], AIBudget.day <= period['end']).all()
    active_ids = db.query(Activity.account_id).filter(
        Activity.created_at >= cutoff, Activity.created_at < until, Activity.outcome < 400,
    )
    admins.audit(db, admin, 'overview.read')
    return {
        **period,
        'ai_usage': {
            'calls': sum(c.calls for c in ai), 'input_tokens': sum(c.input_tokens for c in ai),
            'output_tokens': sum(c.output_tokens for c in ai),
            'estimated_usd': sum(c.actual_microusd for c in ai) / 1000000,
            'reserved_usd': sum(c.reserved_microusd for c in ai) / 1000000,
        },
        'totals': {
            'accounts': customer_accounts(db).count(), 'new_accounts': sum(registrations.values()),
            'applications': db.query(Application).join(Session, Application.session_id == Session.id).filter(
                Session.owner_id.in_(customer_accounts(db).with_entities(Account.id)),
                Application.updated_at >= cutoff, Application.updated_at < until,
            ).count(),
            'page_views': sum(m.page_views for m in metrics), 'visit_sessions': sum(m.visits for m in metrics),
            'active_accounts': customer_accounts(db).filter(Account.id.in_(active_ids)).count(),
            'pending_verifications': customer_accounts(db).outerjoin(AccountSecurity, Account.id == AccountSecurity.account_id).filter(AccountSecurity.verified_at.is_(None)).count(),
            'verified_users': customer_accounts(db).join(AccountSecurity, Account.id == AccountSecurity.account_id).filter(AccountSecurity.verified_at.is_not(None)).count(),
        },
        'email_delivery': {
            'pending': db.query(EmailOutbox).filter(EmailOutbox.status.in_(['pending', 'sending'])).count(),
            'failed': db.query(EmailOutbox).filter_by(status='failed').count(),
            'sent': db.query(EmailOutbox).filter_by(status='sent').count(), 'retention_days': 7,
            'measurement': 'Zustellmetadaten, keine Nachrichteninhalte. Fehlgeschlagen umfasst auch abgelaufene oder ersetzte Links.',
        },
        'daily': [
            {'day': day, 'page_views': next((m.page_views for m in metrics if m.day == day), 0),
             'visit_sessions': next((m.visits for m in metrics if m.day == day), 0), 'registrations': registrations.get(day, 0)}
            for day in [(cutoff + timedelta(days=index)).date().isoformat() for index in range(period['days'])]
        ],
        'operations': [{'event': event, 'count': count} for event, count in activity],
        'measurement': 'UTC-Kalendertage. Kunden ohne Betreiberkonten. Aufrufe und gestartete App-Sitzungen sind keine eindeutigen Menschen. Geräte, Länder und aktive Zeit im Traffic-Tab werden erst ab Einwilligung und Einführung der neuen Statistik erfasst.',
    }


@router.get('/traffic')
def traffic(
    days: int = Query(30, ge=1, le=90), start: str | None = Query(None, max_length=10),
    end: str | None = Query(None, max_length=10), offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100), admin=Depends(protected), db=Depends(get_db),
):
    from backend.services.traffic_service import summarize
    cutoff, until, period = date_range(admins.now(), days, start, end)
    admins.audit(db, admin, 'traffic.read')
    return {**summarize(db, cutoff, until, limit=limit, offset=offset), **period}


@router.get('/users')
def users(
    q: str = Query('', max_length=254), status: str = Query('all', pattern='^(all|pending|verified|active|new)$'),
    days: int = Query(30, ge=1, le=90), start: str | None = Query(None, max_length=10),
    end: str | None = Query(None, max_length=10), offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100), admin=Depends(protected), db=Depends(get_db),
):
    cutoff, until, period = date_range(admins.now(), days, start, end)
    query = customer_accounts(db).outerjoin(AccountProfile, Account.id == AccountProfile.account_id).outerjoin(AccountSecurity, Account.id == AccountSecurity.account_id)
    if q.strip():
        name = func.coalesce(AccountProfile.first_name, '') + ' ' + func.coalesce(AccountProfile.last_name, '')
        query = query.filter(or_(Account.email.contains(q.strip().lower(), autoescape=True),
            name.contains(q.strip(), autoescape=True), AccountProfile.display_name.contains(q.strip(), autoescape=True)))
    if status == 'pending':
        query = query.filter(AccountSecurity.verified_at.is_(None))
    elif status == 'verified':
        query = query.filter(AccountSecurity.verified_at.is_not(None))
    elif status == 'new':
        query = query.filter(Account.created_at >= cutoff, Account.created_at < until)
    elif status == 'active':
        query = query.filter(Account.id.in_(db.query(Activity.account_id).filter(
            Activity.created_at >= cutoff, Activity.created_at < until, Activity.outcome < 400)))
    total = query.count()
    rows = query.order_by(Account.created_at.desc(), Account.id).offset(offset).limit(limit).all()
    ids = [row.id for row in rows]
    usage = dict(db.query(Activity.account_id, func.max(Activity.created_at)).filter(Activity.account_id.in_(ids)).group_by(Activity.account_id).all())
    projects = dict(db.query(Session.owner_id, func.count(Application.id)).join(Application, Application.session_id == Session.id).filter(Session.owner_id.in_(ids)).group_by(Session.owner_id).all())
    from backend.services import admin_support as support
    admins.audit(db, admin, 'users.read')
    items = []
    for row in rows:
        detail = support.user_details(db, row)
        profile = detail['profile']
        security = db.get(AccountSecurity, row.id)
        items.append({
            'id': row.id, 'email': row.email, 'created_at': row.created_at.isoformat(),
            'last_active_at': usage[row.id].isoformat() if row.id in usage else None,
            'applications': projects.get(row.id, 0), 'display_name': profile['display_name'],
            'first_name': profile['first_name'], 'last_name': profile['last_name'], 'phone': profile['phone'],
            **detail,
            'verified_at': security.verified_at.isoformat() + 'Z' if security and security.verified_at else None,
            'verification_source': security.verification_source if security else None,
        })
    return {'total': total, 'offset': offset, 'status': status, **period, 'items': items}


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
    security = db.get(AccountSecurity, account.id)
    profile = db.get(AccountProfile, account.id)
    from backend.services import admin_support as support
    return {
        "id": account.id,
        "email": account.email,
        "created_at": account.created_at.isoformat(),
        "display_name": profile.display_name if profile else "",
        **support.user_details(db, account),
        "verified_at": security.verified_at.isoformat() + "Z"
        if security and security.verified_at else None,
        "verification_source": security.verification_source if security else None,
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


@router.patch('/users/{account_id}/profile')
def edit_user_profile(account_id: str, req: 'AdminProfilePatch', admin=Depends(protected), db=Depends(get_db)):
    from backend.services import admin_support as support
    return support.update_profile(db, admin, account_id, req)


@router.post('/users/{account_id}/password-reset')
def support_reset(account_id: str, req: 'AdminPasswordResetRequest', admin=Depends(protected), db=Depends(get_db)):
    from backend.services import admin_support as support
    return support.request_password_reset(db, admin, account_id, req)


@router.get('/applications')
def application_list(
    start: str | None = Query(None, max_length=10), end: str | None = Query(None, max_length=10),
    offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
    admin=Depends(protected), db=Depends(get_db),
):
    from backend.services import admin_application
    cutoff, until, period = date_range(admins.now(), 30, start, end)
    query = db.query(Application, Account.email).join(Session, Application.session_id == Session.id).join(Account, Session.owner_id == Account.id).filter(
        Session.owner_id.in_(customer_accounts(db).with_entities(Account.id)),
    )
    if start is not None:
        query = query.filter(Application.updated_at >= cutoff, Application.updated_at < until)
    total = query.count()
    admins.audit(db, admin, 'applications.read')
    items = []
    for project, email in query.order_by(Application.updated_at.desc(), Application.id).offset(offset).limit(limit):
        value = admin_application.project_json(db, project)
        value.pop('data')
        items.append({**value, 'email': email})
    return {'total': total, 'offset': offset, **period, 'items': items}


@router.patch('/applications/{project_id}')
def edit_application(project_id: str, req: ApplicationPatch, admin=Depends(protected), db=Depends(get_db)):
    from backend.services import admin_application
    return admin_application.modify(db, admin, project_id, req)


@router.get("/applications/{project_id}")
def application(project_id: str, admin=Depends(protected), db=Depends(get_db)):
    project = db.get(Application, project_id)
    if not project:
        raise HTTPException(404, "Bewerbung nicht gefunden")
    admins.audit(db, admin, "application.content.read", project_id)
    from backend.services import admin_application
    return admin_application.project_json(db, project)


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
    start: str | None = Query(None, max_length=10),
    end: str | None = Query(None, max_length=10),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    admin=Depends(protected),
    db=Depends(get_db),
):
    cutoff, until, _period = date_range(admins.now(), 30, start, end)
    query = db.query(Session)
    if start is not None:
        query = query.filter(Session.created_at >= cutoff, Session.created_at < until)
    query = query.order_by(Session.created_at.desc(), Session.id)
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
    start: str | None = Query(None, max_length=10),
    end: str | None = Query(None, max_length=10),
    account_id: str = Query("", max_length=36),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin=Depends(protected),
    db=Depends(get_db),
):
    query = db.query(Activity, Account.email).outerjoin(Account, Activity.account_id == Account.id)
    cutoff, until, _period = date_range(admins.now(), 30, start, end)
    if start is not None:
        query = query.filter(Activity.created_at >= cutoff, Activity.created_at < until)
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
    start: str | None = Query(None, max_length=10),
    end: str | None = Query(None, max_length=10),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin=Depends(protected),
    db=Depends(get_db),
):
    admins.audit(db, admin, "audit.read")
    query = db.query(AdminAudit, Account.email).outerjoin(
        Account, AdminAudit.admin_id == Account.id
    )
    cutoff, until, _period = date_range(admins.now(), 30, start, end)
    if start is not None:
        query = query.filter(AdminAudit.created_at >= cutoff, AdminAudit.created_at < until)
    return {
        "total": query.count(),
        "items": [
            {
                "id": row.id,
                "email": email,
                "action": row.action,
                "subject_id": row.subject_id,
                "reason": row.reason,
                "changed_fields": json.loads(row.changed_fields_json or "[]"),
                "created_at": row.created_at.isoformat(),
            }
            for row, email in query.order_by(AdminAudit.created_at.desc(), AdminAudit.id)
            .offset(offset)
            .limit(limit)
        ],
    }


@router.get("/database")
def database(admin=Depends(protected), db=Depends(get_db)):
    from backend.analytics_models import TrafficDaily, TrafficVisit
    models = [
        TrafficDaily, TrafficVisit,
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
        AccountSecurity,
        AccountProfile,
        EmailOutbox,
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
