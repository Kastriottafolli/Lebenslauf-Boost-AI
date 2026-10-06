"""UTC reporting windows, customer-only totals and distinct account status filters."""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.account_models import AccountProfile, AccountSecurity
from backend.config import get_settings
from backend.database import Base, get_db
from backend.main import app
from backend.models import (
    Account,
    Activity,
    AdminAccess,
    AdminLogin,
    Application,
    DailyMetric,
    Session,
)
from backend.services import admin_service as admins
from backend.services.admin_dates import date_range
from backend.services.session_service import token_hash

NOW = datetime(2026, 10, 6, 12)
START = datetime(2026, 10, 6)
UNTIL = datetime(2026, 10, 7)


@pytest.fixture
def reporting(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "reporting.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(get_settings(), "hosted_ai_enabled", False)
    monkeypatch.setattr(get_settings(), "operator_email", "info@tafolli.net")
    monkeypatch.setattr(admins, "now", lambda: NOW)
    with factory() as db:
        accounts = {
            "admin": Account(email="admin@example.com", created_at=START),
            "operator": Account(email="info@tafolli.net", created_at=START),
            "old": Account(email="old@example.com", created_at=datetime(2026, 1, 1)),
            "new": Account(email="new@example.com", created_at=START),
            "last": Account(email="last@example.com", created_at=UNTIL - timedelta(microseconds=1)),
            "after": Account(email="after@example.com", created_at=UNTIL),
        }
        for account in accounts.values():
            account.password_hash, account.recovery_hash = "synthetic-password-hash", "synthetic-recovery-hash"
        db.add_all(accounts.values())
        db.flush()
        ids = {key: value.id for key, value in accounts.items()}
        db.add_all([
            AdminAccess(account_id=ids["admin"], enabled=True, secret_cipher="synthetic-mfa"),
            AdminLogin(token_hash=token_hash("reporting-admin"), account_id=ids["admin"], expires_at=NOW + timedelta(minutes=10)),
            AccountProfile(account_id=ids["old"], first_name="Ada", last_name="Lovelace", display_name="Ada"),
            AccountSecurity(account_id=ids["new"], verification_source="email_pending"),
        ])
        for key in ("old", "last", "after", "operator", "admin"):
            db.add(AccountSecurity(account_id=ids[key], verified_at=START, verification_source="email_confirmed"))
        for key, created, outcome in (
            ("old", START - timedelta(microseconds=1), 200), ("old", START, 200),
            ("last", UNTIL - timedelta(microseconds=1), 200), ("after", UNTIL, 200),
            ("new", NOW, 422), ("admin", NOW, 200), ("operator", NOW, 200),
        ):
            db.add(Activity(account_id=ids[key], event="project.open", outcome=outcome, created_at=created))
        for key, updated in (
            ("old", START), ("last", UNTIL - timedelta(microseconds=1)),
            ("after", UNTIL), ("admin", NOW), ("operator", NOW),
        ):
            sess = Session(owner_id=ids[key], created_at=updated)
            db.add(sess)
            db.flush()
            db.add(Application(session_id=sess.id, title=key, data_json='{"_revision":1}', updated_at=updated))
        db.add_all([
            DailyMetric(day="2026-10-05", page_views=5, visits=2),
            DailyMetric(day="2026-10-06", page_views=7, visits=3),
            DailyMetric(day="2026-10-07", page_views=99, visits=99),
        ])
        db.commit()

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    client = TestClient(app, headers={"X-Boosty-Request": "1", "Authorization": "Bearer reporting-admin"})
    yield client, factory, ids
    app.dependency_overrides.clear()
    engine.dispose()


def test_today_and_yesterday_are_complete_utc_calendar_days():
    first, until, period = date_range(NOW, days=1)
    assert (first, until) == (START, UNTIL)
    assert period == {"start": "2026-10-06", "end": "2026-10-06", "days": 1, "timezone": "UTC"}
    first, until, period = date_range(NOW, start="2026-10-05", end="2026-10-05")
    assert (first, until) == (START - timedelta(days=1), START)
    assert period["days"] == 1
    first, until, period = date_range(NOW, start="2024-01-01", end="2024-12-31")
    assert period["days"] == 366 and (until - first).days == 366


@pytest.mark.parametrize("options", [
    {"start": "2026-10-06"}, {"end": "2026-10-06"},
    {"start": "2026-10-07", "end": "2026-10-06"},
    {"start": "2025-02-29", "end": "2025-02-29"},
    {"start": "2026-1-01", "end": "2026-01-01"},
    {"start": "", "end": ""}, {"start": "2024-01-01", "end": "2025-01-01"},
    {"start": "9999-12-31", "end": "9999-12-31"}, {"days": 0}, {"days": 367},
])
def test_invalid_or_oversized_date_ranges_reject_with_422(options):
    with pytest.raises(HTTPException) as error:
        date_range(NOW, **options)
    assert error.value.status_code == 422


def test_overview_bounds_are_inclusive_start_exclusive_end_and_exclude_operators(reporting):
    client, _factory, _ids = reporting
    response = client.get("/api/admin/overview?start=2026-10-06&end=2026-10-06")
    assert response.status_code == 200
    data = response.json()
    assert data["days"] == 1 and data["timezone"] == "UTC"
    assert data["totals"] == {
        "accounts": 4, "new_accounts": 2, "applications": 2,
        "page_views": 7, "visit_sessions": 3, "active_accounts": 2,
        "pending_verifications": 1, "verified_users": 3,
    }
    assert data["daily"] == [{"day": "2026-10-06", "page_views": 7, "visit_sessions": 3, "registrations": 2}]


def test_yesterday_and_zero_data_custom_period_keep_zero_daily_rows(reporting):
    client, _factory, _ids = reporting
    yesterday = client.get("/api/admin/overview?start=2026-10-05&end=2026-10-05").json()
    assert yesterday["daily"] == [{"day": "2026-10-05", "page_views": 5, "visit_sessions": 2, "registrations": 0}]
    zero = client.get("/api/admin/overview?start=2026-10-01&end=2026-10-02").json()
    assert zero["days"] == 2 and zero["totals"]["accounts"] == 4
    assert all(zero["totals"][key] == 0 for key in ("new_accounts", "active_accounts", "applications", "page_views", "visit_sessions"))
    assert zero["daily"] == [
        {"day": "2026-10-01", "page_views": 0, "visit_sessions": 0, "registrations": 0},
        {"day": "2026-10-02", "page_views": 0, "visit_sessions": 0, "registrations": 0},
    ]


def test_new_and_active_filters_have_distinct_window_semantics_and_search_names(reporting):
    client, _factory, ids = reporting
    query = "start=2026-10-06&end=2026-10-06"
    expected = {"all": {"old", "new", "last", "after"}, "new": {"new", "last"},
                "active": {"old", "last"}, "pending": {"new"}, "verified": {"old", "last", "after"}}
    for status, keys in expected.items():
        response = client.get(f"/api/admin/users?status={status}&{query}")
        assert response.status_code == 200
        assert response.json()["total"] == len(keys)
        assert {row["id"] for row in response.json()["items"]} == {ids[key] for key in keys}
    name = client.get("/api/admin/users?q=Ada%20Lovelace").json()
    assert name["total"] == 1 and name["items"][0]["first_name"] == "Ada"
    assert client.get("/api/admin/users?q=%25").json()["total"] == 0
    assert client.get("/api/admin/users?status=administrator").status_code == 422


@pytest.mark.parametrize("route", ["overview", "users", "traffic", "applications", "sessions", "events", "audit"])
def test_report_routes_require_real_admin_session_and_complete_dates(reporting, route):
    client, _factory, _ids = reporting
    anonymous = TestClient(app, headers={"X-Boosty-Request": "1"})
    assert anonymous.get("/api/admin/" + route).status_code == 401
    assert client.get("/api/admin/" + route + "?start=2026-10-06").status_code == 422
    assert client.get("/api/admin/" + route + "?start=2026-10-06&end=2026-10-05").status_code == 422


def test_dated_sessions_events_and_applications_include_only_selected_calendar_days(reporting):
    client, _factory, ids = reporting
    query = "?start=2026-10-06&end=2026-10-06"
    projects = client.get("/api/admin/applications" + query).json()
    assert projects["total"] == 2 and {row["title"] for row in projects["items"]} == {"old", "last"}
    sessions = client.get("/api/admin/sessions" + query).json()
    assert sessions["total"] == 4 and all(row["owner_id"] != ids["after"] for row in sessions["items"])
    events = client.get("/api/admin/events" + query).json()
    assert events["total"] == 5
    assert all(row["created_at"].startswith("2026-10-06") for row in events["items"])
