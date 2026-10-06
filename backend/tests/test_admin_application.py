"""Support document edits preserve application facts and use one audited revision."""

import json
from copy import deepcopy
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings
from backend.database import Base, get_db
from backend.main import app
from backend.models import (
    Account,
    AdminAccess,
    AdminAudit,
    AdminLogin,
    Application,
    PackageReservation,
    Session,
)
from backend.services import account_service as accounts
from backend.services import admin_application as applications
from backend.services.session_service import token_hash

DOCUMENTS = {key: f"Original complete {key} document" for key in applications.DOCUMENT_KEYS}
ORIGINAL = {
    "_revision": 3, "_created_at": "2026-01-01T12:00:00Z", "_generated_at": "2026-01-02T12:00:00Z",
    "title": "Original title", "status": "draft", "notes": "Original notes", "language": "sq", "design": "modern",
    "profile": {"name": "Synthetic person", "source_text": "Only confirmed original work experience", "confirmed": True},
    "job": {"title": "Original job", "company": "Original company", "description": "Original confirmed job requirements"},
    "documents": DOCUMENTS, "wishes": "Keep original wishes", "photo": "synthetic-profile-photo", "step": 4,
    "extension": {"keep": [1, 2, 3]},
}


@pytest.fixture
def application_db(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "application-support.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(get_settings(), "hosted_ai_enabled", False)
    with factory() as db:
        admin = Account(email="admin@example.com", password_hash="synthetic-hash", recovery_hash="synthetic-recovery")
        user = Account(email="ordinary@example.com", password_hash="synthetic-hash", recovery_hash="synthetic-recovery")
        reserved = Account(email="info@tafolli.net", password_hash="synthetic-hash", recovery_hash="synthetic-recovery")
        db.add_all([admin, user, reserved])
        db.flush()
        ids = {"admin": admin.id, "user": user.id, "reserved": reserved.id}
        db.add_all([
            AdminAccess(account_id=admin.id, enabled=True, secret_cipher="synthetic-mfa"),
            AdminLogin(token_hash=token_hash("application-admin"), account_id=admin.id, expires_at=accounts.now() + timedelta(minutes=10)),
        ])
        for key, owner in (("own", user.id), ("other", user.id), ("admin_project", admin.id), ("reserved_project", reserved.id), ("guest", None)):
            sess = Session(owner_id=owner)
            db.add(sess)
            db.flush()
            project = Application(session_id=sess.id, title="Original title", status="draft", data_json=json.dumps(deepcopy(ORIGINAL)))
            db.add(project)
            db.flush()
            ids[key] = project.id
        for key in ("own", "other"):
            db.add(PackageReservation(account_id=user.id, project_id=ids[key], request_id=key, fingerprint="f" * 64,
                status="completed", response_json=json.dumps({"documents": DOCUMENTS}),
                response_expires_at=accounts.now() + timedelta(hours=1), expires_at=accounts.now() + timedelta(hours=1)))
        db.commit()

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app, headers={"X-Boosty-Request": "1"}), factory, ids
    app.dependency_overrides.clear()
    engine.dispose()


def request(**changes):
    return applications.ApplicationPatch(expected_revision=3, reason="Customer requested document correction", **changes)


def test_support_merges_only_allowlisted_fields_preserves_facts_and_purges_only_own_cache(application_db):
    _client, factory, ids = application_db
    corrected_cv = "Corrected CV with customer supplied facts"
    with factory() as db:
        result = applications.modify(db, db.get(Account, ids["admin"]), ids["own"], request(
            title=" New title ", status="ready", notes="Customer-approved notes", documents={"cv": corrected_cv},
        ))
        assert result["revision"] == 4 and result["editable"] is True
        assert (result["title"], result["status"]) == ("New title", "ready")
        expected = deepcopy(ORIGINAL)
        expected.update(_revision=4, title="New title", status="ready", notes="Customer-approved notes")
        expected["documents"]["cv"] = corrected_cv
        assert result["data"] == expected
        assert json.loads(db.get(Application, ids["other"]).data_json) == ORIGINAL
        own_cache = db.query(PackageReservation).filter_by(project_id=ids["own"]).one()
        assert own_cache.response_json is None and own_cache.response_expires_at is None
        assert own_cache.status == "completed" and own_cache.fingerprint == "f" * 64
        assert db.query(PackageReservation).filter_by(project_id=ids["other"]).one().response_json is not None
        audit = db.query(AdminAudit).one()
        assert audit.action == "application.support.updated" and audit.subject_id == ids["own"]
        assert audit.admin_id == ids["admin"] and audit.reason == "Customer requested document correction"
        assert set(json.loads(audit.changed_fields_json)) == {"title", "status", "notes", "documents.cv"}
        assert corrected_cv not in audit.changed_fields_json


def test_stale_revision_or_concurrent_save_preserves_latest_project_and_has_no_success_audit(application_db):
    _client, factory, ids = application_db
    with factory() as db:
        with pytest.raises(HTTPException) as error:
            applications.modify(db, db.get(Account, ids["admin"]), ids["own"], applications.ApplicationPatch(
                expected_revision=2, reason="Customer correction requested", notes="A stale draft"))
        assert error.value.status_code == 409 and error.value.detail["code"] == "APPLICATION_CONFLICT"
        assert db.query(AdminAudit).count() == 0
    with factory() as stale:
        stale_project = stale.get(Application, ids["own"])
        with factory() as current:
            newest = deepcopy(ORIGINAL)
            newest.update(_revision=4, notes="Latest user notes")
            current.get(Application, ids["own"]).data_json = json.dumps(newest)
            current.commit()
        assert json.loads(stale_project.data_json)["_revision"] == 3
        with pytest.raises(HTTPException) as error:
            applications.modify(stale, stale.get(Account, ids["admin"]), ids["own"], request(notes="Stale support notes"))
        assert error.value.status_code == 409 and error.value.detail["code"] == "APPLICATION_CONFLICT"
        assert json.loads(stale.get(Application, ids["own"]).data_json) == newest
        assert stale.query(AdminAudit).count() == 0


def test_noop_does_not_increment_revision_audit_or_erase_cached_response(application_db):
    _client, factory, ids = application_db
    with factory() as db:
        result = applications.modify(db, db.get(Account, ids["admin"]), ids["own"], request(title="Original title", documents={"cv": DOCUMENTS["cv"]}))
        assert result["revision"] == 3 and result["data"] == ORIGINAL
        assert db.query(AdminAudit).count() == 0
        assert db.query(PackageReservation).filter_by(project_id=ids["own"]).one().response_json is not None


@pytest.mark.parametrize("target", ["admin_project", "reserved_project", "guest"])
def test_support_never_edits_admin_reserved_or_unowned_projects(application_db, target):
    _client, factory, ids = application_db
    with factory() as db:
        assert applications.project_json(db, db.get(Application, ids[target]))["editable"] is False
        with pytest.raises(HTTPException) as error:
            applications.modify(db, db.get(Account, ids["admin"]), ids[target], request(notes="Forbidden edit"))
        assert error.value.status_code == 403
        assert json.loads(db.get(Application, ids[target]).data_json) == ORIGINAL
        assert db.query(AdminAudit).count() == 0


def test_regular_or_disabled_admin_actor_and_missing_project_are_rejected(application_db):
    _client, factory, ids = application_db
    with factory() as db:
        with pytest.raises(HTTPException) as error:
            applications.modify(db, db.get(Account, ids["user"]), ids["own"], request(notes="Forbidden"))
        assert error.value.status_code == 403
        with pytest.raises(HTTPException) as error:
            applications.modify(db, db.get(Account, ids["admin"]), "missing-project", request(notes="Missing"))
        assert error.value.status_code == 404
        db.get(AdminAccess, ids["admin"]).enabled = False
        db.commit()
        with pytest.raises(HTTPException) as error:
            applications.modify(db, db.get(Account, ids["admin"]), ids["own"], request(notes="Forbidden"))
        assert error.value.status_code == 403 and db.query(AdminAudit).count() == 0


@pytest.mark.parametrize("fields", [
    {}, {"title": "   "}, {"title": "x" * 201}, {"status": "admin"}, {"notes": "x" * 4001},
    {"documents": {}}, {"documents": {"unknown": "Ignored text"}}, {"documents": {"cv": ""}},
    {"documents": {"cv": "short"}}, {"documents": {"cv": " " * 10}}, {"documents": {"cv": "x" * 60001}},
    {"documents": {"cv": " " * 60000 + "A sufficiently long document"}},
    {"profile": {"name": "Injected"}}, {"job": {"description": "Injected"}}, {"owner_id": "admin"},
])
def test_application_patch_rejects_invalid_packages_and_non_allowlisted_fact_edits(fields):
    with pytest.raises(ValidationError):
        request(**fields)


def test_absent_documents_require_complete_valid_package_and_preserve_legacy_metadata(application_db):
    _client, factory, ids = application_db
    with factory() as db:
        legacy = deepcopy(ORIGINAL)
        legacy.pop("documents")
        legacy.pop("_revision")
        project = db.get(Application, ids["own"])
        project.data_json = json.dumps(legacy)
        db.commit()
        partial = applications.ApplicationPatch(expected_revision=0, reason="Customer supplied full package", documents={"cv": "A sufficiently long new CV"})
        with pytest.raises(HTTPException) as error:
            applications.modify(db, db.get(Account, ids["admin"]), ids["own"], partial)
        assert error.value.status_code == 422 and json.loads(project.data_json) == legacy
        assert db.query(AdminAudit).count() == 0
        complete = applications.ApplicationPatch(expected_revision=0, reason="Customer supplied full package", documents=DOCUMENTS)
        result = applications.modify(db, db.get(Account, ids["admin"]), ids["own"], complete)
        assert result["revision"] == 1 and result["data"]["documents"] == DOCUMENTS
        for key in ("profile", "job", "_created_at", "_generated_at", "extension"):
            assert result["data"][key] == legacy[key]


def test_route_requires_admin_session_and_audit_response_exposes_only_reason_and_field_names(application_db):
    client, _factory, ids = application_db
    body = {"expected_revision": 3, "reason": "Customer requested support correction", "notes": "Approved support note"}
    url = f"/api/admin/applications/{ids['own']}"
    assert client.patch(url, json=body).status_code == 401
    headers = {"Authorization": "Bearer application-admin"}
    assert client.patch(url, json={**body, "role": "admin"}, headers=headers).status_code == 422
    response = client.patch(url, json=body, headers=headers)
    assert response.status_code == 200 and response.json()["revision"] == 4
    assert client.patch(url, json=body, headers=headers).status_code == 409
    assert client.patch(f"/api/admin/applications/{ids['admin_project']}", json=body, headers=headers).status_code == 403
    audit = client.get("/api/admin/audit", headers=headers)
    assert audit.status_code == 200
    row = next(item for item in audit.json()["items"] if item["action"] == "application.support.updated")
    assert row["reason"] == body["reason"] and row["changed_fields"] == ["notes"]
    assert "Approved support note" not in audit.text
