"""Audited, revision-protected support edits to owned application documents."""
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import update

from backend.models import Account, AdminAccess, AdminAudit, Application, Session
from backend.profile_schema import SupportReason
from backend.services import admin_support, billing_service

DOCUMENT_KEYS = frozenset({'cv', 'cover_letter', 'motivation_letter', 'email'})


class ApplicationPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0)
    reason: SupportReason
    title: str | None = Field(None, min_length=1, max_length=200)
    status: str | None = Field(None, pattern='^(draft|ready|sent|interview|offer|rejected)$')
    notes: str | None = Field(None, max_length=4000)
    documents: dict[str, str] | None = None

    @model_validator(mode='after')
    def changes(self):
        if self.documents is not None and (
            not self.documents or not set(self.documents).issubset(DOCUMENT_KEYS)
            or any(len(value.strip()) < 10 or len(value) > 60000 for value in self.documents.values())
        ):
            raise ValueError('Ungültige Dokumentfelder / invalid document fields')
        if not any(getattr(self, field) is not None for field in ('title', 'status', 'notes', 'documents')):
            raise ValueError('Mindestens eine Änderung erforderlich / no changes')
        if self.title is not None:
            self.title = self.title.strip()
            if not self.title:
                raise ValueError('Titel erforderlich / title required')
        return self


def editable(db, project):
    sess = db.get(Session, project.session_id)
    account = db.get(Account, sess.owner_id) if sess and sess.owner_id else None
    return bool(account and not db.get(AdminAccess, account.id) and not admin_support._reserved(account))


def project_json(db, project):
    data = json.loads(project.data_json)
    return {
        'id': project.id, 'title': project.title, 'status': project.status,
        'updated_at': project.updated_at.isoformat() + 'Z', 'revision': data.get('_revision', 0),
        'editable': editable(db, project), 'data': data,
    }


def modify(db, admin, project_id, req):
    admin_support._actor(db, admin)
    project = db.get(Application, project_id)
    if not project:
        raise HTTPException(404, 'Bewerbung nicht gefunden / application not found')
    if not editable(db, project):
        raise HTTPException(403, 'Nur Bewerbungen gewöhnlicher Nutzerkonten sind im Support bearbeitbar')
    original = project.data_json
    data = json.loads(original)
    revision = data.get('_revision', 0)
    if req.expected_revision != revision:
        raise HTTPException(409, {'code': 'APPLICATION_CONFLICT', 'message': 'Die Bewerbung wurde inzwischen geändert. Aktuellen Stand laden.', 'revision': revision})
    changed = []
    for field in ('title', 'status', 'notes'):
        value = getattr(req, field)
        previous = getattr(project, field) if field in ('title', 'status') else data.get(field, '')
        if value is not None and value != previous:
            data[field] = value
            changed.append(field)
    if req.documents is not None:
        documents = dict(data.get('documents') or {})
        for key, value in req.documents.items():
            if documents.get(key) != value:
                documents[key] = value
                changed.append('documents.' + key)
        if set(documents) != DOCUMENT_KEYS or any(
            not isinstance(value, str) or len(value.strip()) < 10 or len(value) > 60000
            for value in documents.values()
        ):
            raise HTTPException(422, 'Ein vollständiges Paket mit vier lesbaren Dokumenten ist erforderlich')
        data['documents'] = documents
    if not changed:
        return project_json(db, project)
    data['_revision'] = revision + 1
    current = datetime.now(UTC).replace(tzinfo=None)
    result = db.execute(update(Application).where(Application.id == project_id, Application.data_json == original).values(
        data_json=json.dumps(data, ensure_ascii=False), title=data.get('title', project.title),
        status=data.get('status', project.status), updated_at=current,
    ).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, {'code': 'APPLICATION_CONFLICT', 'message': 'Die Bewerbung wurde inzwischen geändert.'})
    billing_service.purge_cached_responses(db, project_ids=[project_id])
    db.add(AdminAudit(admin_id=admin.id, action='application.support.updated', subject_id=project_id,
        reason=req.reason, changed_fields_json=json.dumps(changed)))
    db.commit()
    db.refresh(project)
    return project_json(db, project)
