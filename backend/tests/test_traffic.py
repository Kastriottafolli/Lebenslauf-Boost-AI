"""Consent, ownership, offline lookup, duration bounds and independent retention."""

import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.analytics_models import TrafficDaily, TrafficVisit, init_traffic_schema
from backend.database import Base, get_db
from backend.routers.traffic import router
from backend.services import traffic_service as traffic


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/traffic.db", connect_args={"check_same_thread": False})
    init_traffic_schema(engine)
    factory = sessionmaker(bind=engine)
    clock = [datetime(2026, 10, 6, 12, 0)]
    settings = SimpleNamespace(traffic_geoip_db_path="", traffic_store_masked_ip=True)
    monkeypatch.setattr(traffic, "now", lambda: clock[0])
    monkeypatch.setattr(traffic.time, "monotonic", lambda: clock[0].timestamp())
    monkeypatch.setattr(traffic, "get_settings", lambda: settings)
    traffic._rate_buckets.clear()
    traffic._country_cache = None
    app = FastAPI()
    app.include_router(router)

    def dependency():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    client = TestClient(app, client=("8.8.8.8", 12345))
    yield client, factory, clock, settings
    traffic._rate_buckets.clear()
    traffic._country_cache = None
    engine.dispose()


def consent_start(client, **kwargs):
    response = client.post("/api/traffic/start", json={"page": "home", "analytics_consent": True, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()["visit_token"]


def report(client, token, active, *, end=False, **extra):
    return client.post("/api/traffic/end" if end else "/api/traffic/heartbeat", json={"visit_token": token, "active_seconds": active, **extra})


def summary(factory, clock, days=1, **kwargs):
    with factory() as db:
        end = clock[0].replace(hour=0, minute=0, second=0) + timedelta(days=1)
        return traffic.summarize(db, end - timedelta(days=days), end, current=clock[0], **kwargs)


@pytest.mark.parametrize("value", [False, "true", "yes", 1, None])
def test_no_detail_without_explicit_boolean_consent(env, value):
    client, factory, _clock, _settings = env
    response = client.post("/api/traffic/start", json={"page": "home", "analytics_consent": value})
    assert response.status_code == 422
    assert client.post("/api/traffic/start", json={"page": "home"}).status_code == 422
    with factory() as db:
        assert db.query(TrafficVisit).count() == db.query(TrafficDaily).count() == 0


@pytest.mark.parametrize("page", ["admin", "/", "/home?email=private@example.com", "https://example.com"])
def test_accepts_only_fixed_public_page_labels(env, page):
    client, factory, _clock, _settings = env
    assert client.post("/api/traffic/start", json={"page": page, "analytics_consent": True}).status_code == 422
    with factory() as db:
        assert db.query(TrafficVisit).count() == 0


def test_server_peer_only_and_no_identifying_payload_retention(env, monkeypatch):
    client, factory, clock, _settings = env
    addresses = []

    def lookup(address):
        addresses.append(address)
        return "FR"

    monkeypatch.setattr(traffic, "country_for_ip", lookup)
    response = client.post("/api/traffic/start", headers={
        "User-Agent": "Synthetic iPhone Mobile PrivateBrowserFingerprint",
        "X-Forwarded-For": "1.1.1.1", "X-Real-IP": "1.1.1.1",
        "Referer": "https://example.com/account?email=private@example.com",
    }, json={"page": "home", "analytics_consent": True, "country": "DE", "ip": "1.1.1.1", "account_id": "private-account", "fingerprint": "private-browser"})
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    token = response.json()["visit_token"]
    assert len(token) == 43 and addresses == ["8.8.8.8"]
    with factory() as db:
        visit = db.query(TrafficVisit).one()
        assert visit.device == "mobile" and visit.country_code == "FR"
        assert visit.ip_masked == "8.8.8.0/24"
        assert visit.token_hash != token and len(visit.token_hash) == 64
        stored = str(db.execute(text("SELECT * FROM traffic_visits")).all())
        for forbidden in (token, "8.8.8.8", "1.1.1.1", "PrivateBrowserFingerprint", "private@example.com", "private-account", "private-browser"):
            assert forbidden not in stored
        columns = {column["name"] for column in inspect(db.get_bind()).get_columns("traffic_visits")}
        assert not columns & {"account_id", "user_agent", "ip", "referrer", "url", "fingerprint"}
    result = summary(factory, clock)
    assert result["countries"] == [{"country": "FR", "visits": 1, "active_seconds": 0, "elapsed_seconds": 0}]
    assert result["items"][0]["started_at"].endswith("+00:00")
    assert "token_hash" not in str(result) and token not in str(result)


@pytest.mark.parametrize("ua,expected", [
    ("Mozilla Desktop", "desktop"), ("Mozilla iPhone Mobile", "mobile"),
    ("Mozilla iPad", "tablet"), ("Mozilla Android Tablet", "tablet"),
    ("Mozilla Googlebot Mobile", "bot"), ("x" * 512 + "iPhone", "desktop"),
])
def test_coarse_device_from_bounded_user_agent(ua, expected):
    assert traffic.device_from_user_agent(ua) == expected


def test_ipv4_ipv6_masking_and_optional_collection(env):
    client, factory, _clock, settings = env
    assert traffic.mask_ip("203.0.113.159") == "203.0.113.0/24"
    assert traffic.mask_ip("2001:db8:1234:5678:9abc::1") == "2001:db8:1234::/48"
    assert traffic.mask_ip("::ffff:203.0.113.159") == "203.0.113.0/24"
    assert traffic.mask_ip("bad-input") is None
    settings.traffic_store_masked_ip = False
    consent_start(client)
    with factory() as db:
        assert db.query(TrafficVisit).one().ip_masked is None


def test_country_unknown_invalid_or_private_never_fabricated(env):
    _client, factory, clock, _settings = env
    for address, lookup in (("8.8.8.8", lambda _ip: "XX"), ("8.8.4.4", lambda _ip: "Germany"), ("127.0.0.1", lambda _ip: pytest.fail("Private IP should not be looked up"))):
        with factory() as db:
            traffic.start(db, page="home", analytics_consent=True, client_ip=address, country_lookup=lookup, current=clock[0])
    assert summary(factory, clock)["countries"][0]["country"] is None


def test_local_country_db1_file_is_functional_and_optional(env, tmp_path):
    _client, _factory, _clock, settings = env
    path = tmp_path / "IP2LOCATION-LITE-DB1.CSV"
    path.write_text('"134744064","134744319","US","United States"\n"16843008","16843263","AU","Australia"\n')
    settings.traffic_geoip_db_path = str(path)
    assert traffic.country_for_ip("8.8.8.8") == "US"
    assert traffic.country_for_ip("1.1.1.1") == "AU"
    assert traffic.country_for_ip("9.9.9.9") is None
    assert traffic.country_for_ip("2001:4860:4860::8888") is None
    assert traffic.country_status()["available"] is True
    path.unlink()
    assert traffic.country_for_ip("8.8.8.8") is None
    assert traffic.country_status()["available"] is False


def test_offline_mmdb_uses_local_reader_and_validates_country_codes(env, tmp_path, monkeypatch):
    import sys

    _client, _factory, _clock, settings = env
    path = tmp_path / "country.mmdb"
    path.write_bytes(b"local-database-fixture")
    settings.traffic_geoip_db_path = str(path)
    opened, addresses = [], []

    class Reader:
        def get(self, address):
            addresses.append(address)
            return {"country": {"iso_code": "DE" if address == "8.8.8.8" else "ZZ"}}

        def close(self):
            pass

    def open_database(filename):
        opened.append(filename)
        return Reader()

    monkeypatch.setitem(sys.modules, "maxminddb", SimpleNamespace(open_database=open_database))
    assert traffic.country_for_ip("8.8.8.8") == "DE"
    assert traffic.country_for_ip("9.9.9.9") is None
    assert opened == [str(path)] and addresses == ["8.8.8.8", "9.9.9.9"]


def test_racing_duplicate_pulses_credit_activity_only_once(env, monkeypatch):
    client, factory, clock, _settings = env
    token = consent_start(client)
    clock[0] += timedelta(seconds=15)
    original = traffic._visit_for_token
    barrier = threading.Barrier(2)
    thread_state = threading.local()

    def synchronize_first_read(db, token, current):
        result = original(db, token, current)
        if not getattr(thread_state, "read", False):
            thread_state.read = True
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(traffic, "_visit_for_token", synchronize_first_read)

    def pulse():
        with factory() as db:
            return traffic.pulse(db, token=token, active_seconds=15)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _value: pulse(), range(2)))
    assert all(result["active_seconds"] == 15 for result in results)
    with factory() as db:
        assert db.query(TrafficVisit).one().active_seconds == 15
        assert db.query(TrafficDaily).one().active_seconds == 15


def test_engagement_is_cumulative_clipped_to_wall_time_and_replay_safe(env):
    client, factory, clock, _settings = env
    token = consent_start(client)
    clock[0] += timedelta(seconds=15)
    assert report(client, token, 1000).json()["active_seconds"] == 15
    # Duplicate or an older pulse must not credit the same cumulative activity again.
    clock[0] += timedelta(seconds=15)
    assert report(client, token, 1000).json()["active_seconds"] == 15
    assert report(client, token, 999).json()["active_seconds"] == 15
    clock[0] += timedelta(minutes=10)
    response = report(client, token, 2000)
    assert response.json()["active_seconds"] == 45
    assert response.json()["elapsed_seconds"] == 630
    clock[0] += timedelta(seconds=2)
    assert report(client, token, 2100, end=True).json() == {"ok": True, "active_seconds": 47, "elapsed_seconds": 632, "ended": True}
    clock[0] += timedelta(minutes=1)
    assert report(client, token, 2200).json()["active_seconds"] == 47
    result = summary(factory, clock)
    assert result["totals"]["active_seconds"] == 47
    assert result["totals"]["elapsed_seconds"] == 632
    assert result["items"][0]["ended_at"] is not None


def test_realistic_pulses_and_utc_day_attribution(env):
    client, factory, clock, _settings = env
    clock[0] = datetime(2026, 10, 6, 23, 59, 50)
    token = consent_start(client)
    clock[0] += timedelta(seconds=15)
    assert report(client, token, 15).json()["active_seconds"] == 15
    clock[0] += timedelta(seconds=15)
    assert report(client, token, 30, end=True).json()["active_seconds"] == 30
    result = summary(factory, clock, days=2)
    assert result["daily"] == [
        {"day": "2026-10-06", "visits": 1, "active_seconds": 30, "elapsed_seconds": 30},
        {"day": "2026-10-07", "visits": 0, "active_seconds": 0, "elapsed_seconds": 0},
    ]
    assert result["totals"]["avg_active_seconds"] == 30


def test_capability_ownership_expiry_and_validated_counters(env):
    client, factory, clock, _settings = env
    token = consent_start(client)
    other = secrets.token_urlsafe(32)
    assert report(client, other, 15).status_code == 404
    assert client.post("/api/traffic/end", json={"visit_token": other, "withdraw": True}).status_code == 404
    for bad in (-1, 86401, "15", True, 1.5):
        assert report(client, token, bad).status_code == 422
    assert report(client, "../malformed-token", 0).status_code == 422
    clock[0] += timedelta(hours=24)
    assert report(client, token, 86400).status_code == 404
    with factory() as db:
        assert db.query(TrafficVisit).one().active_seconds == 0


def test_withdrawal_deletes_detail_and_its_aggregate_contribution(env):
    client, factory, clock, _settings = env
    token = consent_start(client)
    clock[0] += timedelta(seconds=15)
    assert report(client, token, 15).status_code == 200
    assert client.post("/api/traffic/end", json={"visit_token": token, "withdraw": True}).json() == {"ok": True, "withdrawn": True}
    assert report(client, token, 30).status_code == 404
    with factory() as db:
        assert db.query(TrafficVisit).count() == 0
    result = summary(factory, clock)
    assert result["total"] == result["totals"]["visits"] == result["totals"]["active_seconds"] == 0


def test_separate_mask_detail_and_anonymous_aggregate_retention(env):
    client, factory, clock, _settings = env
    token = consent_start(client)
    clock[0] += timedelta(seconds=15)
    report(client, token, 15, end=True)
    clock[0] += timedelta(days=8)
    result = summary(factory, clock, days=9)
    assert result["items"][0]["ip_masked"] is None  # Hidden even before scheduled cleanup.
    with factory() as db:
        assert traffic.cleanup(db)["masked_ips_cleared"] == 1
        db.commit()
        visit = db.query(TrafficVisit).one()
        assert visit.ip_masked is None and visit.token_hash is None and visit.token_expires_at is None
    clock[0] += timedelta(days=23)
    with factory() as db:
        assert traffic.cleanup(db)["visits_deleted"] == 1
        db.commit()
        assert db.query(TrafficVisit).count() == 0
        assert db.query(TrafficDaily).one().visits == 1
    result = summary(factory, clock, days=32)
    assert result["total"] == 0 and result["totals"]["visits"] == 1
    clock[0] += timedelta(days=60)
    with factory() as db:
        assert traffic.cleanup(db)["aggregate_rows_deleted"] == 1
        db.commit()
        assert db.query(TrafficDaily).count() == 0


def test_summary_has_bounded_pagination_and_page_filter(env):
    client, factory, clock, _settings = env
    consent_start(client, page="home")
    clock[0] += timedelta(seconds=1)
    consent_start(client, page="app")
    clock[0] += timedelta(seconds=1)
    consent_start(client, page="app")
    result = summary(factory, clock, page="app", limit=1, offset=1)
    assert result["total"] == result["totals"]["visits"] == 2
    assert len(result["items"]) == 1 and result["items"][0]["page"] == "app"
    for kwargs in ({"limit": 101}, {"offset": -1}, {"page": "admin"}):
        with pytest.raises(ValueError):
            summary(factory, clock, **kwargs)
    with factory() as db, pytest.raises(ValueError):
        traffic.summarize(db, clock[0] - timedelta(days=91), clock[0])


def test_peer_and_token_budgets_are_bounded_and_withdrawal_still_works(env):
    client, _factory, _clock, _settings = env
    token = consent_start(client)
    for _ in range(12):
        assert report(client, token, 0).status_code == 200
    limited = report(client, token, 0)
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
    assert client.post("/api/traffic/end", json={"visit_token": token, "withdraw": True}).status_code == 200
    for _ in range(19):
        consent_start(client)
    assert client.post("/api/traffic/start", json={"page": "home", "analytics_consent": True}).status_code == 429
    with pytest.raises(HTTPException):
        traffic.limit_request("8.8.8.8", "start")


def test_telemetry_storage_failure_is_nonfatal_and_logs_no_client_data(env, monkeypatch, caplog):
    client, _factory, _clock, _settings = env

    def broken(*_args, **_kwargs):
        raise RuntimeError("private 8.8.8.8 exception text")

    monkeypatch.setattr(traffic, "start", broken)
    response = client.post("/api/traffic/start", json={"page": "home", "analytics_consent": True})
    assert response.status_code == 200 and response.json() == {"ok": False, "disabled": True}
    assert "private" not in caplog.text and "8.8.8.8" not in caplog.text


def test_schema_addition_preserves_existing_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE legacy_example (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO legacy_example VALUES ('preserved')"))
    init_traffic_schema(engine)
    init_traffic_schema(engine)
    with engine.begin() as connection:
        assert connection.execute(text("SELECT value FROM legacy_example")).scalar() == "preserved"
    assert {"traffic_visits", "traffic_daily", "legacy_example"} <= set(inspect(engine).get_table_names())
    engine.dispose()


@pytest.fixture
def integrated(env, monkeypatch):
    from backend import database
    from backend.config import get_settings
    from backend.routers import ALL_ROUTERS, frontend
    from backend.security import install_security

    _client, factory, clock, settings = env
    Base.metadata.create_all(factory.kw["bind"])
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(get_settings(), "hosted_ai_enabled", True)
    app = FastAPI()
    install_security(app)
    for registered in ALL_ROUTERS:
        app.include_router(registered)
    assert ALL_ROUTERS.index(router) < ALL_ROUTERS.index(frontend.router)

    def dependency():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    return TestClient(app, base_url="https://testserver", client=("8.8.8.8", 12345)), factory, clock, settings


def test_integrated_traffic_remains_public_with_hosted_login_required(integrated):
    client, factory, clock, _settings = integrated
    response = client.post("/api/traffic/start", json={"page": "home", "analytics_consent": True}, headers={"Origin": "https://testserver"})
    assert response.status_code == 200 and response.json()["ok"] is True
    assert response.headers["cache-control"] == "no-store" and "set-cookie" not in response.headers
    token = response.json()["visit_token"]
    clock[0] += timedelta(seconds=15)
    assert report(client, token, 15).json()["active_seconds"] == 15
    assert report(client, token, 15, end=True).json()["ended"] is True
    # The login exemption is exact: it does not expose other API paths.
    assert client.post("/api/traffic/private", json={}).status_code == 401
    with factory() as db:
        assert db.query(TrafficVisit).count() == 1


def test_integrated_origin_and_validation_boundaries(integrated):
    client, factory, _clock, _settings = integrated
    payload = {"page": "home", "analytics_consent": True}
    assert client.post("/api/traffic/start", json=payload, headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert client.post("/api/traffic/start", json=payload, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/traffic/start", json={"page": "home", "analytics_consent": False}).status_code == 422
    assert client.post("/api/traffic/start", content="invalid-json", headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/api/traffic/start", json={**payload, "page": "admin"}).status_code == 422
    with factory() as db:
        assert db.query(TrafficVisit).count() == 0


def test_integrated_admin_traffic_is_private_even_for_normal_accounts(integrated):
    from backend.account_models import AccountSecurity
    from backend.models import Account, Login
    from backend.services.session_service import token_hash

    client, factory, _clock, _settings = integrated
    assert client.get("/api/admin/traffic").status_code == 403
    assert client.get("/api/admin/traffic", headers={"X-Boosty-Request": "1"}).status_code == 401
    token = secrets.token_urlsafe(32)
    current = datetime.now(UTC).replace(tzinfo=None)
    with factory() as db:
        account = Account(email="traffic-customer@example.com", password_hash="test-only", recovery_hash="test-only")
        db.add(account)
        db.flush()
        db.add(AccountSecurity(account_id=account.id, verified_at=current, verification_source="email_confirmed"))
        db.add(Login(token_hash=token_hash(token), account_id=account.id, expires_at=current + timedelta(hours=1)))
        db.commit()
    assert client.get("/api/admin/traffic", headers={"X-Boosty-Request": "1", "Authorization": "Bearer " + token}).status_code == 401


def test_database_initialization_and_existing_cleanup_include_traffic(env, monkeypatch):
    from backend import cleanup as installed_cleanup
    from backend import database

    _client, factory, _clock, _settings = env
    monkeypatch.setattr(database, "engine", factory.kw["bind"])
    monkeypatch.setattr(database, "database_path", None)
    monkeypatch.setattr(installed_cleanup, "SessionLocal", factory)
    database.init_db()
    assert {"traffic_visits", "traffic_daily"} <= set(inspect(factory.kw["bind"]).get_table_names())
    current = datetime.now(UTC).replace(tzinfo=None)
    with factory() as db:
        traffic.start(db, page="home", analytics_consent=True, client_ip="8.8.8.8", current=current - timedelta(days=8))
    assert installed_cleanup.cleanup() == 0
    with factory() as db:
        visit = db.query(TrafficVisit).one()
        assert visit.ip_masked is None and visit.token_hash is None
        assert db.query(TrafficDaily).count() == 1
