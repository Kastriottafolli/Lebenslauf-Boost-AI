"""Profiles, job import, application packages, accounts and owned projects."""

import json
import re
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from backend import schemas
from backend.database import get_db
from backend.llm import llm_service
from backend.models import Account, AdminAccess, Application, Login, Session
from backend.services import account_service as accounts
from backend.services import application_service as applications
from backend.services import job_service, session_service

router = APIRouter(tags=["Application platform"])


class Profile(BaseModel):
    name: str = Field("", max_length=200)
    email: str = Field("", max_length=254)
    phone: str = Field("", max_length=100)
    location: str = Field("", max_length=300)
    headline: str = Field("", max_length=300)
    experience: str = Field("", max_length=12000)
    education: str = Field("", max_length=6000)
    skills: str = Field("", max_length=6000)
    languages: str = Field("", max_length=1000)
    source_text: str = Field(..., min_length=10, max_length=60000)
    confirmed: bool = False


class Job(BaseModel):
    description: str = Field(..., min_length=10, max_length=20000)
    title: str = Field("", max_length=200)
    company: str = Field("", max_length=200)
    recipient: str = Field("", max_length=200)
    email: str = Field("", max_length=254)
    url: str = Field("", max_length=2000)


class PackageRequest(BaseModel):
    session_id: str
    profile: Profile
    job: Job
    wishes: str = Field("", max_length=4000)
    language: str = Field("de", pattern="^(de|en)$")
    provider: str = Field("openai", pattern="^(openai|claude|gemini|grok|azure)$")
    model: str = Field("", max_length=100)
    endpoint: str = Field("", max_length=300)
    keys: schemas.ApiKeys = Field(default_factory=schemas.ApiKeys)
    demo: bool = False


class PackageRefine(PackageRequest):
    document: str = Field(..., pattern="^(cv|cover_letter|motivation_letter|email)$")
    current_content: str = Field(..., min_length=10, max_length=60000)
    instruction: str = Field(..., min_length=2, max_length=4000)


class URLRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2000)


class SourceRequest(BaseModel):
    source_text: str = Field(..., min_length=10, max_length=60000)


@router.post("/api/profile/parse")
def parse_profile(req: SourceRequest):
    return applications.parse_profile(req.source_text)


@router.post("/api/job/import")
def import_job(req: URLRequest):
    return job_service.import_job(req.url)


@router.post("/api/package")
def build_package(
    req: PackageRequest,
    db: DBSession = Depends(get_db),
    x_session_token: str = Header(""),
):
    session_service.get_session(db, req.session_id, x_session_token)
    return applications.build_package(req)


@router.post("/api/package/refine")
def refine_package(
    req: PackageRefine,
    db: DBSession = Depends(get_db),
    x_session_token: str = Header(""),
):
    session_service.get_session(db, req.session_id, x_session_token)
    if not req.profile.confirmed:
        raise HTTPException(422, "Profil zuerst bestätigen / confirm profile")
    if req.demo:
        raise HTTPException(
            422,
            "Freie Umformulierungen benötigen einen API-Key. Text direkt bearbeiten / edit text directly in demo.",
        )
    provider = llm_service.get_provider(
        req.provider, req.keys.model_dump(), req.model, req.endpoint
    )
    if not provider.available():
        raise HTTPException(422, "API-Key fehlt / missing key")
    result = provider.generate(
        applications.system_prompt(req.language, req.document),
        [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "confirmed_profile": req.profile.model_dump(),
                        "job": req.job.model_dump(),
                        "document": req.document,
                        "current_draft": req.current_content,
                        "revision": req.instruction,
                    },
                    ensure_ascii=False,
                ),
            }
        ],
    )
    return {"content": result.content, "model": result.model}


class Credentials(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=12, max_length=128)

    def normalized_email(self):
        value = self.email.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise HTTPException(422, "E-Mail prüfen / check email")
        return value


@router.post("/api/account/register")
def register(
    req: Credentials, request: Request, response: Response, db: DBSession = Depends(get_db)
):
    email = req.normalized_email()
    if db.query(Account).filter_by(email=email).first():
        raise HTTPException(
            409,
            "Registrierung nicht möglich. Anmelden oder Wiederherstellung nutzen / sign in or recover account.",
        )
    recovery = secrets.token_urlsafe(32)
    account = Account(
        email=email,
        password_hash=accounts.password_hash(req.password),
        recovery_hash=session_service.token_hash(recovery),
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Registrierung nicht möglich. Anmelden oder Wiederherstellung nutzen / sign in or recover account.",
        ) from None
    token = accounts.login_cookie(db, account, response)
    request.state.metric_account = account.id
    return {"email": email, "recovery_code": recovery, "access_token": token}


@router.post("/api/account/login")
def login(req: Credentials, request: Request, response: Response, db: DBSession = Depends(get_db)):
    accounts.limit_identity(db, req.normalized_email())
    account = db.query(Account).filter_by(email=req.normalized_email()).first()
    # Perform a password hash even for unknown users.
    stored = account.password_hash if account else accounts.DUMMY_HASH
    if (
        not accounts.password_matches(req.password, stored)
        or not account
        or db.get(AdminAccess, account.id)
    ):
        raise HTTPException(401, "Anmeldedaten ungültig / invalid credentials")
    if not account.password_hash.startswith("scrypt$"):
        account.password_hash = accounts.password_hash(req.password)
    token = accounts.login_cookie(db, account, response)
    request.state.metric_account = account.id
    return {"email": account.email, "access_token": token}


class Recovery(Credentials):
    recovery_code: str = Field(..., min_length=20, max_length=100)


@router.post("/api/account/recover")
def recover(req: Recovery, db: DBSession = Depends(get_db)):
    accounts.limit_identity(db, req.normalized_email(), "recover")
    account = db.query(Account).filter_by(email=req.normalized_email()).first()
    if (
        not account
        or db.get(AdminAccess, account.id)
        or not secrets.compare_digest(
            account.recovery_hash, session_service.token_hash(req.recovery_code)
        )
    ):
        raise HTTPException(401, "Wiederherstellung fehlgeschlagen / recovery failed")
    code = secrets.token_urlsafe(32)
    account.password_hash = accounts.password_hash(req.password)
    account.recovery_hash = session_service.token_hash(code)
    db.query(Login).filter_by(account_id=account.id).delete()
    db.commit()
    return {"recovery_code": code}


@router.get("/api/account")
def account_info(request: Request, db: DBSession = Depends(get_db)):
    account = accounts.current_account(db, request)
    return {"email": account.email if account else None}


@router.post("/api/account/logout")
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ") or request.cookies.get(
        "candidaro_login", ""
    )
    db.query(Login).filter_by(token_hash=session_service.token_hash(token)).delete()
    db.commit()
    response.delete_cookie("candidaro_login", path="/")
    return {"ok": True}


@router.delete("/api/account")
def delete_account(request: Request, response: Response, db: DBSession = Depends(get_db)):
    account = accounts.current_account(db, request, True)
    for sess in db.query(Session).filter_by(owner_id=account.id).all():
        db.query(Application).filter_by(session_id=sess.id).delete()
        db.delete(sess)
    db.query(Login).filter_by(account_id=account.id).delete()
    db.delete(account)
    db.commit()
    response.delete_cookie("candidaro_login", path="/")
    return {"deleted": True}


class ProjectRequest(BaseModel):
    session_id: str
    title: str = Field(..., min_length=1, max_length=200)
    status: str = Field("draft", pattern="^(draft|ready|sent|interview|offer|rejected)$")
    profile: Profile
    job: Job
    documents: dict[str, str]
    language: str = Field("de", pattern="^(de|en)$")
    notes: str = Field("", max_length=4000)


@router.post("/api/projects")
def save_project(
    req: ProjectRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    x_session_token: str = Header(""),
):
    account = accounts.current_account(db, request, True)
    sess = session_service.get_session(db, req.session_id, x_session_token)
    if sess.owner_id and sess.owner_id != account.id:
        raise HTTPException(403, "Zugriff verweigert / access denied")
    if set(req.documents) != set(applications.DOCUMENTS) or any(
        len(v) > 60000 for v in req.documents.values()
    ):
        raise HTTPException(422, "Ungültige Dokumente / invalid documents")
    sess.owner_id = account.id
    project = Application(
        session_id=sess.id,
        title=req.title,
        status=req.status,
        data_json=req.model_dump_json(),
    )
    db.add(project)
    db.commit()
    return {"id": project.id}


def owned_project(db, account, project_id):
    project = (
        db.query(Application)
        .join(Session, Session.id == Application.session_id)
        .filter(Application.id == project_id, Session.owner_id == account.id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Bewerbung nicht gefunden / application not found")
    return project


@router.get("/api/projects")
def list_projects(request: Request, db: DBSession = Depends(get_db)):
    account = accounts.current_account(db, request, True)
    projects = (
        db.query(Application)
        .join(Session, Session.id == Application.session_id)
        .filter(Session.owner_id == account.id)
        .order_by(Application.updated_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "title": p.title,
            "status": p.status,
            "updated_at": p.updated_at.isoformat(),
        }
        for p in projects
    ]


@router.get("/api/projects/{project_id}")
def load_project(project_id: str, request: Request, db: DBSession = Depends(get_db)):
    project = owned_project(db, accounts.current_account(db, request, True), project_id)
    return json.loads(project.data_json)


@router.put("/api/projects/{project_id}")
def update_project(
    project_id: str,
    req: ProjectRequest,
    request: Request,
    db: DBSession = Depends(get_db),
):
    project = owned_project(db, accounts.current_account(db, request, True), project_id)
    if set(req.documents) != set(applications.DOCUMENTS) or any(
        len(v) > 60000 for v in req.documents.values()
    ):
        raise HTTPException(422, "Ungültige Dokumente / invalid documents")
    project.data_json = req.model_dump_json()
    project.title, project.status = req.title, req.status
    project.updated_at = datetime.now(UTC)
    db.commit()
    return {"id": project.id}


@router.delete("/api/projects/{project_id}")
def delete_project(project_id: str, request: Request, db: DBSession = Depends(get_db)):
    project = owned_project(db, accounts.current_account(db, request, True), project_id)
    db.delete(project)
    db.commit()
    return {"deleted": True}


@router.delete("/api/session/{session_id}")
def delete_session(
    session_id: str, db: DBSession = Depends(get_db), x_session_token: str = Header("")
):
    sess = session_service.get_session(db, session_id, x_session_token)
    db.query(Application).filter_by(session_id=sess.id).delete()
    db.delete(sess)
    db.commit()
    return {"deleted": True}


class ProviderTest(BaseModel):
    provider: str = Field(..., pattern="^(openai|claude|gemini|grok|azure)$")
    model: str = Field("", max_length=100)
    endpoint: str = Field("", max_length=300)
    keys: schemas.ApiKeys


@router.post("/api/provider/test")
def test_provider(req: ProviderTest):
    provider = llm_service.get_provider(
        req.provider, req.keys.model_dump(), req.model, req.endpoint
    )
    # Testing keys must always use the user's supplied key, never a server key.
    config = llm_service.PROVIDERS[req.provider]
    if not req.keys.model_dump().get(config["key"]):
        raise HTTPException(422, "API-Key fehlt / missing key")
    result = provider.generate(
        "Return only OK.", [{"role": "user", "content": "Connection test. Return OK."}]
    )
    return {"ok": True, "model": result.model}


@router.get("/api/public-config")
def public_config():
    from backend.config import get_settings

    settings = get_settings()
    return {
        "operator_name": settings.operator_name,
        "operator_address": settings.operator_address,
        "operator_email": settings.operator_email,
        "retention_days": settings.retention_days,
    }


class UsageRequest(BaseModel):
    session_id: str = Field(..., max_length=36)
    event: str = Field(
        ..., pattern="^(demo.generate|document.export|project.backup|profile.confirm)$"
    )


@router.post("/api/usage")
def usage(
    req: UsageRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    x_session_token: str = Header(""),
):
    from backend.models import Activity

    session_service.get_session(db, req.session_id, x_session_token)
    account = accounts.current_account(db, request)
    db.add(Activity(event=req.event, outcome=200, account_id=account.id if account else None))
    db.commit()
    return {"ok": True}
