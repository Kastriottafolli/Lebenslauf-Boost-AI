"""Credits remain bounded under concurrent retries; money cannot be browser-asserted."""

import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings
from backend.database import Base
from backend.llm.base import LLMResult
from backend.models import (
    Account,
    Application,
    CreditLedger,
    PackageReservation,
    PaymentOrder,
    Session,
)
from backend.services import billing_service as billing
from backend.services import hosted_ai
from backend.services import payment_service as payments


@pytest.fixture
def store(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "billing_free_packages", 3)
    monkeypatch.setattr(settings, "billing_payments_enabled", False)
    monkeypatch.setattr(settings, "billing_environment", "sandbox")
    monkeypatch.setattr(settings, "site_url", "https://tafolliboost.com")
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    monkeypatch.setattr(settings, "paypal_client_id", "")
    monkeypatch.setattr(settings, "paypal_client_secret", "")
    monkeypatch.setattr(settings, "paypal_webhook_id", "")
    monkeypatch.setattr(settings, "paypal_merchant_id", "")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'billing.sqlite3'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def configure(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        account = Account(
            email="billing@example.invalid", password_hash="synthetic", recovery_hash="synthetic"
        )
        db.add(account)
        db.commit()
        account_id = account.id
    yield factory, account_id, settings
    engine.dispose()


def test_welcome_is_lifetime_and_additive_for_existing_accounts(store, monkeypatch):
    factory, account_id, settings = store
    with factory() as db:
        assert billing.balance(db, account_id) == {
            "available": 3,
            "reserved": 0,
            "free_total": 3,
            "used": 0,
        }
        original = billing._now()
        monkeypatch.setattr(billing, "_now", lambda: original + timedelta(days=1000))
        monkeypatch.setattr(settings, "billing_free_packages", 8)
        assert billing.balance(db, account_id)["available"] == 3
        assert billing.balance(db, account_id)["free_total"] == 3
        assert db.query(CreditLedger).filter_by(account_id=account_id, kind="welcome").count() == 1


def test_three_packages_only_and_success_replays_without_extra_credit(store):
    factory, account_id, _settings = store
    with factory() as db:
        keys = [uuid4() for _ in range(3)]
        for key in keys:
            lease, cached = billing.reserve_package(db, account_id, key, {"job": str(key)})
            assert cached is None
            billing.complete_package(db, account_id, lease, {"documents": {"cv": "verified draft"}})
        lease, cached = billing.reserve_package(db, account_id, keys[0], {"job": str(keys[0])})
        assert lease is None and cached["documents"]["cv"] == "verified draft"
        with pytest.raises(HTTPException) as depleted:
            billing.reserve_package(db, account_id, uuid4(), {})
        assert (
            depleted.value.status_code == 402
            and depleted.value.detail["code"] == "CREDITS_EXHAUSTED"
        )
        with pytest.raises(HTTPException) as conflict:
            billing.reserve_package(db, account_id, keys[0], {"job": "different"})
        assert conflict.value.detail["code"] == "IDEMPOTENCY_CONFLICT"
        assert billing.balance(db, account_id) == {
            "available": 0,
            "reserved": 0,
            "free_total": 3,
            "used": 3,
        }
        assert sum(row.delta for row in db.query(CreditLedger).all()) == 0


def test_failure_refund_and_retry_are_idempotent(store):
    factory, account_id, _settings = store
    with factory() as db:
        key = uuid4()
        lease, _ = billing.reserve_package(db, account_id, key, {"job": "same"})
        with pytest.raises(HTTPException) as pending:
            billing.reserve_package(db, account_id, key, {"job": "same"})
        assert pending.value.detail["code"] == "PACKAGE_IN_PROGRESS"
        billing.refund_package(db, account_id, lease)
        billing.refund_package(db, account_id, lease)
        assert billing.balance(db, account_id)["available"] == 3
        retry, _ = billing.reserve_package(db, account_id, key, {"job": "same"})
        assert retry.attempt == 2
        billing.refund_package(db, account_id, lease)
        assert billing.balance(db, account_id)["available"] == 2
        billing.complete_package(db, account_id, retry, {"done": True})
        assert billing.balance(db, account_id)["used"] == 1


def test_parallel_writers_cannot_spend_same_credits(store):
    factory, account_id, _settings = store

    def reserve(_index):
        with factory() as db:
            try:
                billing.reserve_package(db, account_id, uuid4(), {})
                return 200
            except HTTPException as failure:
                return failure.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(reserve, range(10)))
    assert statuses.count(200) == 3 and statuses.count(402) == 7
    with factory() as db:
        assert billing.balance(db, account_id)["available"] == 0
        assert billing.balance(db, account_id)["reserved"] == 3
        assert db.query(CreditLedger).filter_by(kind="welcome").count() == 1


def test_worker_abort_refund_has_attempt_fencing(store, monkeypatch):
    factory, account_id, _settings = store
    with factory() as db:
        key = uuid4()
        lease, _ = billing.reserve_package(db, account_id, key, {})
        original = billing._now()
        monkeypatch.setattr(billing, "_now", lambda: original + timedelta(minutes=11))
        assert billing.balance(db, account_id)["available"] == 3
        retry, _ = billing.reserve_package(db, account_id, key, {})
        with pytest.raises(HTTPException) as expired:
            billing.complete_package(db, account_id, lease, {"old": True})
        assert expired.value.detail["code"] == "PACKAGE_RESERVATION_EXPIRED"
        billing.refund_package(db, account_id, lease)
        billing.complete_package(db, account_id, retry, {"new": True})
        assert billing.balance(db, account_id)["available"] == 2


def test_hosted_provider_failure_and_invalid_documents_refund(store, monkeypatch):
    from backend.routers.platform import PackageRequest
    from backend.services.application_service import parse_profile
    from backend.tests.test_platform import JOB, SOURCE

    factory, account_id, settings = store
    monkeypatch.setattr(settings, "openai_api_key", "synthetic")
    with factory() as db:
        sess = Session(owner_id=account_id)
        db.add(sess)
        db.commit()
        session_id = sess.id
    req = PackageRequest(
        session_id=session_id,
        request_id=uuid4(),
        consent=True,
        profile={**parse_profile(SOURCE), "confirmed": True},
        job=JOB,
    )

    def unavailable(*_args, **_kwargs):
        raise HTTPException(502, "Synthetic provider failure")

    with factory() as db:
        account = db.get(Account, account_id)
        monkeypatch.setattr(hosted_ai.Provider, "generate", unavailable)
        with pytest.raises(HTTPException):
            hosted_ai.generate_package(db, account, req)
        assert billing.balance(db, account_id)["available"] == 3
        monkeypatch.setattr(
            hosted_ai.Provider, "generate", lambda *_a, **_kw: LLMResult("{}", "openai", "test")
        )
        with pytest.raises(HTTPException):
            hosted_ai.generate_package(db, account, req)
        assert billing.balance(db, account_id)["available"] == 3
        assert db.query(PackageReservation).one().status == "refunded"


def test_payments_inactive_even_with_partial_credentials_make_no_calls(store, monkeypatch):
    factory, account_id, settings = store
    monkeypatch.setattr(
        payments, "_client", lambda: pytest.fail("Inactive payments must not access network")
    )
    with factory() as db:
        assert payments.pricing()["payments_enabled"] is False
        for enabled in (False, True):
            monkeypatch.setattr(settings, "billing_payments_enabled", enabled)
            with pytest.raises(HTTPException) as unavailable:
                payments.checkout(db, account_id, uuid4(), "stripe", "single")
            assert unavailable.value.status_code == 503
        assert db.query(PaymentOrder).count() == 0


def test_checkout_freezes_server_price_and_reuses_provider_idempotency(store, monkeypatch):
    factory, account_id, settings = store
    _stripe_setup(settings, monkeypatch)
    calls = []

    class Network:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, **kwargs):
            assert url == "https://api.stripe.com/v1/checkout/sessions"
            calls.append(kwargs)
            return httpx.Response(
                200,
                json={"id": "cs_test_order", "url": "https://checkout.stripe.com/order"},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(payments, "_client", Network)
    with factory() as db:
        request_id = uuid4()
        first = payments.checkout(db, account_id, request_id, "stripe", "single")
        monkeypatch.setattr(settings, "billing_single_cents", 300)
        assert payments.checkout(db, account_id, request_id, "stripe", "single") == first
        assert len(calls) == 1
        assert calls[0]["data"]["line_items[0][price_data][unit_amount]"] == "199"
        assert calls[0]["headers"]["Idempotency-Key"] == first["order_id"]
        assert billing.balance(db, account_id)["available"] == 3
        with pytest.raises(HTTPException) as conflict:
            payments.checkout(db, account_id, request_id, "stripe", "bundle10")
        assert conflict.value.detail["code"] == "IDEMPOTENCY_CONFLICT"


def test_payment_redirects_require_exact_provider_host_and_private_https_site(store, monkeypatch):
    _factory, _account_id, settings = store
    _stripe_setup(settings, monkeypatch)
    assert payments._redirect("stripe", "https://checkout.stripe.com/pay/cs")
    for url in (
        "http://checkout.stripe.com/pay",
        "https://checkout.stripe.com.evil.example/pay",
        "https://user@checkout.stripe.com/pay",
        "https://checkout.stripe.com:8443/pay",
    ):
        with pytest.raises(ValueError):
            payments._redirect("stripe", url)
    assert payments._redirect("paypal", "https://www.sandbox.paypal.com/checkoutnow")
    with pytest.raises(ValueError):
        payments._redirect("paypal", "https://www.paypal.com/checkoutnow")
    for site in (
        "http://tafolliboost.com",
        "https://tafolliboost.com:invalid",
        "https://user@tafolliboost.com",
    ):
        monkeypatch.setattr(settings, "site_url", site)
        assert payments.pricing()["payments_enabled"] is False


def _stripe_setup(settings, monkeypatch):
    monkeypatch.setattr(settings, "billing_payments_enabled", True)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_synthetic")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_synthetic")


def _stripe_signature(raw, timestamp=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signed = hmac.new(
        b"whsec_synthetic", timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signed}"


def test_stripe_signature_and_mode_reject_forgery_and_replay_window(store, monkeypatch):
    _factory, _account_id, settings = store
    _stripe_setup(settings, monkeypatch)
    raw = b'{"id":"evt_test","livemode":false,"type":"ignored"}'
    assert payments.verify_stripe(raw, _stripe_signature(raw))["id"] == "evt_test"
    for content, signature in [
        (raw + b" ", _stripe_signature(raw)),
        (raw, _stripe_signature(raw, int(time.time()) - 301)),
        (raw, "t=0,v1=forged"),
    ]:
        with pytest.raises(HTTPException) as denied:
            payments.verify_stripe(content, signature)
        assert denied.value.status_code == 400
    live = b'{"id":"evt_test","livemode":true}'
    with pytest.raises(HTTPException) as denied:
        payments.verify_stripe(live, _stripe_signature(live))
    assert denied.value.detail["code"] == "PAYMENT_ENVIRONMENT_MISMATCH"


def test_paid_stripe_order_credits_exactly_once_and_checks_amount(store, monkeypatch):
    factory, account_id, settings = store
    _stripe_setup(settings, monkeypatch)
    with factory() as db:
        order_id = billing.prepare_order(db, account_id, uuid4(), "stripe", "bundle10")
        billing.save_checkout(
            db, order_id, "cs_test_synthetic", "https://checkout.stripe.com/synthetic"
        )
        verified = {
            "id": "cs_test_synthetic",
            "metadata": {"order_id": order_id},
            "client_reference_id": order_id,
            "mode": "payment",
            "payment_status": "paid",
            "currency": "eur",
            "amount_total": 999,
            "livemode": False,
        }

        class Network:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def get(self, url, **_kwargs):
                assert url == "https://api.stripe.com/v1/checkout/sessions/cs_test_synthetic"
                return httpx.Response(200, json=verified, request=httpx.Request("GET", url))

        monkeypatch.setattr(payments, "_client", Network)

        def payload(event_id):
            return json.dumps(
                {
                    "id": event_id,
                    "livemode": False,
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": "cs_test_synthetic",
                            "metadata": {"order_id": order_id},
                            "payment_status": "paid",
                        }
                    },
                }
            ).encode()

        verified["amount_total"] = 1
        raw = payload("evt_wrong")
        with pytest.raises(HTTPException):
            payments.stripe_webhook(db, raw, _stripe_signature(raw))
        assert billing.balance(db, account_id)["available"] == 3
        verified["amount_total"] = 999
        raw = payload("evt_paid")
        for _ in range(2):
            assert payments.stripe_webhook(db, raw, _stripe_signature(raw))["received"]
        raw = payload("evt_another_delivery")
        payments.stripe_webhook(db, raw, _stripe_signature(raw))
        assert billing.balance(db, account_id)["available"] == 13
        assert db.query(CreditLedger).filter_by(kind="purchase").count() == 1


def test_paypal_verification_preserves_raw_event_and_rejects_mismatched_merchant(
    store, monkeypatch
):
    factory, account_id, settings = store
    for field, value in {
        "billing_payments_enabled": True,
        "paypal_client_id": "synthetic",
        "paypal_client_secret": "synthetic",
        "paypal_webhook_id": "WH-synthetic",
        "paypal_merchant_id": "merchant",
    }.items():
        monkeypatch.setattr(settings, field, value)
    with factory() as db:
        order_id = billing.prepare_order(db, account_id, uuid4(), "paypal", "single")
        billing.save_checkout(
            db, order_id, "ORDER123", "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123"
        )
        event_data = {
            "id": "WH-event",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "CAPTURE",
                "status": "COMPLETED",
                "final_capture": True,
                "payee": {"merchant_id": "wrong"},
                "amount": {"currency_code": "EUR", "value": "1.99"},
                "supplementary_data": {"related_ids": {"order_id": "ORDER123"}},
            },
        }
        headers = {
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-test",
            "paypal-transmission-id": "transmission",
            "paypal-transmission-sig": "signature",
            "paypal-transmission-time": "time",
        }
        verified_status = ["FAILURE"]
        raw_expected = [json.dumps(event_data, indent=2).encode()]

        class Network:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def post(self, url, **kwargs):
                if url.endswith("/v1/oauth2/token"):
                    response = {"access_token": "synthetic-token"}
                else:
                    assert url.endswith("/v1/notifications/verify-webhook-signature")
                    assert kwargs["content"].endswith(raw_expected[0] + b"}")
                    assert json.loads(kwargs["content"])["webhook_id"] == "WH-synthetic"
                    response = {"verification_status": verified_status[0]}
                return httpx.Response(200, json=response, request=httpx.Request("POST", url))

        monkeypatch.setattr(payments, "_client", Network)
        with pytest.raises(HTTPException) as denied:
            payments.paypal_webhook(db, raw_expected[0], headers)
        assert denied.value.detail["code"] == "INVALID_SIGNATURE"
        verified_status[0] = "SUCCESS"
        with pytest.raises(HTTPException) as denied:
            payments.paypal_webhook(db, raw_expected[0], headers)
        assert denied.value.detail["code"] == "PAYMENT_ORDER_MISMATCH"
        event_data["resource"]["payee"]["merchant_id"] = "merchant"
        raw_expected[0] = json.dumps(event_data, indent=2).encode()
        payments.paypal_webhook(db, raw_expected[0], headers)
        payments.paypal_webhook(db, raw_expected[0], headers)
        assert billing.balance(db, account_id)["available"] == 4


def test_account_deletion_cascades_private_package_cache_and_orders(store):
    factory, account_id, _settings = store
    with factory() as db:
        lease, _ = billing.reserve_package(db, account_id, uuid4(), {})
        billing.complete_package(db, account_id, lease, {"documents": {"cv": "private content"}})
        billing.prepare_order(db, account_id, uuid4(), "stripe", "single")
        db.delete(db.get(Account, account_id))
        db.commit()
        assert db.query(PackageReservation).count() == 0
        assert db.query(CreditLedger).count() == 0
        assert db.query(PaymentOrder).count() == 0


def test_http_pricing_balance_package_retries_and_inactive_callbacks(store, monkeypatch):
    from fastapi import Request
    from fastapi.testclient import TestClient

    from backend import database
    from backend.database import get_db
    from backend.main import app
    from backend.routers.platform import Job, Profile
    from backend.services.account_service import current_account
    from backend.services.application_service import demo_package, parse_profile
    from backend.tests.test_platform import JOB, SOURCE, register, session

    factory, _account_id, settings = store
    monkeypatch.setattr(settings, "hosted_ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "synthetic-operator-key")
    monkeypatch.setattr(database, "SessionLocal", factory)

    def isolated_db(request: Request):
        with factory() as db:
            account = current_account(db, request)
            db.info["authenticated_account_id"] = account.id if account else None
            yield db

    app.dependency_overrides[get_db] = isolated_db
    try:
        client = TestClient(app)
        assert client.get("/api/billing/pricing").status_code == 200
        assert client.get("/api/billing/pricing").json()["free_period"] == "lifetime"
        assert client.get("/api/billing/balance").status_code == 401
        for provider in ("stripe", "paypal"):
            assert (
                client.post(f"/api/billing/webhooks/{provider}", content=b"{}").status_code == 503
            )
        register(client)
        sid = session(client)
        assert client.get("/api/billing/balance").json()["available"] == 3
        checkout = {"offer_id": "single", "provider": "stripe", "request_id": str(uuid4())}
        assert client.post("/api/billing/checkout", json=checkout).status_code == 503
        assert (
            client.post("/api/billing/checkout", json={**checkout, "amount_cents": 1}).status_code
            == 422
        )
        docs = demo_package(Profile(**parse_profile(SOURCE)), Job(**JOB), "de")
        calls = []

        def generate(*_args, **_kwargs):
            calls.append(True)
            return LLMResult(json.dumps(docs), "openai", "test")

        monkeypatch.setattr(hosted_ai.Provider, "generate", generate)
        payload = {
            "session_id": sid,
            "request_id": str(uuid4()),
            "consent": True,
            "profile": {**parse_profile(SOURCE), "confirmed": True},
            "job": JOB,
        }
        first = client.post("/api/package", json=payload)
        assert first.status_code == 200, first.text
        replay = client.post("/api/package", json=payload)
        assert replay.json() == first.json() and len(calls) == 1
        assert client.get("/api/account").json()["billing"]["available"] == 2
        assert client.post("/api/package", json={**payload, "wishes": "changed"}).status_code == 409
        for _ in range(2):
            assert (
                client.post(
                    "/api/package", json={**payload, "request_id": str(uuid4())}
                ).status_code
                == 200
            )
        exhausted = client.post("/api/package", json={**payload, "request_id": str(uuid4())})
        assert (
            exhausted.status_code == 402
            and exhausted.json()["detail"]["code"] == "CREDITS_EXHAUSTED"
        )
        assert len(calls) == 3
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def hosted_client(store, monkeypatch):
    from fastapi import Request
    from fastapi.testclient import TestClient

    from backend import database
    from backend.database import get_db
    from backend.main import app
    from backend.routers.platform import Job, Profile
    from backend.services.account_service import current_account
    from backend.services.application_service import demo_package, parse_profile
    from backend.tests.test_platform import JOB, SOURCE, register, session

    factory, _account_id, settings = store
    monkeypatch.setattr(settings, "hosted_ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "synthetic-operator-key")
    monkeypatch.setattr(database, "SessionLocal", factory)

    def isolated_db(request: Request):
        with factory() as db:
            account = current_account(db, request)
            db.info["authenticated_account_id"] = account.id if account else None
            yield db

    app.dependency_overrides[get_db] = isolated_db
    client = TestClient(app)
    registration = register(client)
    payload = {
        "session_id": session(client),
        "request_id": str(uuid4()),
        "consent": True,
        "profile": {**parse_profile(SOURCE), "confirmed": True},
        "job": JOB,
    }
    documents = demo_package(Profile(**parse_profile(SOURCE)), Job(**JOB), "de")
    monkeypatch.setattr(
        hosted_ai.Provider,
        "generate",
        lambda *_a, **_kw: LLMResult(json.dumps(documents), "openai", "test"),
    )
    try:
        yield client, payload, documents, registration
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_lost_response_survives_actual_worker_restart_in_owned_history(
    store, hosted_client, monkeypatch
):
    import os
    import subprocess
    import sys

    factory, _account_id, _settings = store
    client, payload, _documents, registration = hosted_client
    with factory() as db:
        account_id = db.query(Account).filter_by(email=registration["email"]).one().id
    # A separate worker completes the request, loses its response and exits.
    # The replacement worker/browser has neither its Python objects nor request state.
    script = """
import json, os, sys
from backend.config import get_settings
from backend.database import SessionLocal
from backend.models import Account
from backend.llm.base import LLMResult
from backend.routers.platform import PackageRequest
from backend.services import hosted_ai
get_settings().openai_api_key = 'synthetic'
documents = {key: 'Private verified application document' for key in
             ('cv', 'cover_letter', 'motivation_letter', 'email')}
hosted_ai.Provider.generate = lambda *_a, **_kw: LLMResult(json.dumps(documents), 'openai', 'test')
with SessionLocal() as db:
    hosted_ai.generate_package(db, db.get(Account, sys.argv[1]),
                              PackageRequest(**json.load(sys.stdin)))
os._exit(0)
"""
    environment = dict(os.environ)
    environment.update(
        DATABASE_URL=str(factory.kw["bind"].url),
        HOSTED_AI_ENABLED="true",
        OPENAI_API_KEY="",
        BOOSTY_OPENAI_API_KEY="",
    )
    worker = subprocess.run(
        [sys.executable, "-c", script, account_id],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=environment,
        timeout=30,
    )
    assert worker.returncode == 0, worker.stderr
    factory.kw["bind"].dispose()
    restarted = type(client)(client.app)
    restarted.cookies.update(client.cookies)
    restarted.headers.update(client.headers)
    history = restarted.get("/api/projects").json()
    assert len(history) == 1 and history[0]["has_documents"]
    saved = restarted.get("/api/projects/" + history[0]["id"]).json()
    assert saved["documents"]["cv"] == "Private verified application document"
    assert restarted.get("/api/billing/balance").json()["available"] == 2
    monkeypatch.setattr(
        hosted_ai.Provider, "generate", lambda *_a, **_kw: pytest.fail("Replay called AI")
    )
    replay = restarted.post("/api/package", json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["project_id"] == history[0]["id"]
    assert replay.json()["project_revision"] == saved["_revision"] == 1
    assert len(restarted.get("/api/projects").json()) == 1
    assert restarted.get("/api/billing/balance").json()["used"] == 1


def test_generation_promotes_draft_atomically_and_replays_original_revision(hosted_client):
    client, payload, documents, _registration = hosted_client
    draft = {
        "session_id": payload["session_id"],
        "title": "My chosen title",
        "profile": payload["profile"],
        "job": payload["job"],
        "design": "sapphire",
        "notes": "Private note",
        "documents": None,
    }
    initial = client.post("/api/projects", json=draft).json()
    payload.update(project_id=initial["id"], project_revision=initial["revision"])
    generated = client.post("/api/package", json=payload)
    assert generated.status_code == 200, generated.text
    result = generated.json()
    assert result["project_id"] == initial["id"] and result["project_revision"] == 2
    assert len(client.get("/api/projects").json()) == 1
    saved = client.get("/api/projects/" + initial["id"]).json()
    assert saved["documents"] == documents
    assert saved["title"] == draft["title"] and saved["design"] == "sapphire"
    assert saved["notes"] == "Private note" and saved["_generated_at"]
    assert client.post("/api/package", json=payload).json() == result
    edited = {
        **draft,
        "documents": {**documents, "cv": "A later manually edited CV"},
        "revision": 2,
    }
    assert client.put("/api/projects/" + initial["id"], json=edited).json()["revision"] == 3
    assert client.post("/api/package", json=payload).json()["project_revision"] == 2
    assert (
        client.put(
            "/api/projects/" + initial["id"], json={**draft, "documents": documents, "revision": 2}
        ).status_code
        == 409
    )
    assert (
        client.get("/api/projects/" + initial["id"]).json()["documents"]["cv"]
        == edited["documents"]["cv"]
    )


@pytest.mark.parametrize("scope", ["project", "session"])
def test_personal_data_deletion_erases_replay_cache_without_credit_refund(
    store, hosted_client, scope
):
    from backend.routers.platform import PackageRequest

    factory, _account_id, _settings = store
    client, payload, _documents, _registration = hosted_client
    generated = client.post("/api/package", json=payload).json()
    path = (
        "/api/projects/" + generated["project_id"]
        if scope == "project"
        else "/api/session/" + payload["session_id"]
    )
    assert client.delete(path).status_code == 200
    with factory() as db:
        record = db.query(PackageReservation).filter_by(request_id=payload["request_id"]).one()
        assert record.status == "completed" and record.response_json is None
        assert record.response_expires_at is None and record.project_id is None
        if scope == "session":
            assert record.session_id is None
        with pytest.raises(HTTPException) as deleted:
            billing.reserve_package(
                db,
                record.account_id,
                payload["request_id"],
                PackageRequest(**payload).model_dump(mode="json", exclude={"request_id"}),
            )
        assert deleted.value.status_code == 410
        assert billing.balance(db, record.account_id)["available"] == 2
        assert billing.balance(db, record.account_id)["used"] == 1
    if scope == "project":
        replay = client.post("/api/package", json=payload)
        assert replay.status_code == 410
        assert replay.json()["detail"]["code"] == "PACKAGE_REPLAY_UNAVAILABLE"
    assert client.get("/api/projects").json() == []


def test_expired_response_is_purged_but_owned_history_and_spent_credit_remain(
    store, hosted_client, monkeypatch
):
    factory, _account_id, _settings = store
    client, payload, documents, _registration = hosted_client
    result = client.post("/api/package", json=payload).json()
    original = billing._now()
    monkeypatch.setattr(billing, "_now", lambda: original + timedelta(hours=24, seconds=1))
    replay = client.post("/api/package", json=payload)
    assert replay.status_code == 410, replay.text
    assert replay.json()["detail"]["code"] == "PACKAGE_REPLAY_UNAVAILABLE"
    with factory() as db:
        record = db.query(PackageReservation).filter_by(request_id=payload["request_id"]).one()
        assert record.response_json is None and record.status == "completed"
        assert billing.balance(db, record.account_id)["available"] == 2
    assert client.get("/api/projects/" + result["project_id"]).json()["documents"] == documents


def test_credit_completion_failure_rolls_back_owned_application_and_refunds(store, monkeypatch):
    from backend.routers.platform import Job, PackageRequest, Profile
    from backend.services.application_service import demo_package, parse_profile
    from backend.tests.test_platform import JOB, SOURCE

    factory, account_id, settings = store
    monkeypatch.setattr(settings, "openai_api_key", "synthetic")
    documents = demo_package(Profile(**parse_profile(SOURCE)), Job(**JOB), "de")
    monkeypatch.setattr(
        hosted_ai.Provider,
        "generate",
        lambda *_a, **_kw: LLMResult(json.dumps(documents), "openai", "test"),
    )
    with factory() as db:
        sess = Session(owner_id=account_id)
        db.add(sess)
        db.commit()
        req = PackageRequest(
            session_id=sess.id,
            request_id=uuid4(),
            consent=True,
            profile={**parse_profile(SOURCE), "confirmed": True},
            job=JOB,
        )

        @event.listens_for(db, "before_flush")
        def fail_completion(session, _context, _instances):
            if any(
                isinstance(row, PackageReservation) and row.status == "completed"
                for row in session.dirty
            ):
                raise RuntimeError("Synthetic commit failure")

        with pytest.raises(RuntimeError, match="Synthetic commit failure"):
            hosted_ai.generate_package(db, db.get(Account, account_id), req)
        assert db.query(Application).count() == 0
        assert db.query(PackageReservation).one().status == "refunded"
        assert billing.balance(db, account_id)["available"] == 3


def test_billing_tables_initialize_additively_on_existing_account_admin_and_history(
    tmp_path, monkeypatch
):
    from sqlalchemy import inspect

    from backend import database
    from backend.models import AdminAccess

    path = tmp_path / "before-billing.sqlite3"
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def configure(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    new_tables = {
        "credit_wallets",
        "credit_ledger",
        "package_reservations",
        "payment_orders",
        "payment_events",
    }
    Base.metadata.create_all(
        engine,
        tables=[table for table in Base.metadata.sorted_tables if table.name not in new_tables],
    )
    factory = sessionmaker(bind=engine)
    with factory() as db:
        account = Account(
            email="existing@example.invalid", password_hash="old hash", recovery_hash="old recovery"
        )
        db.add(account)
        db.flush()
        sess = Session(owner_id=account.id)
        db.add(sess)
        db.flush()
        project = Application(
            session_id=sess.id,
            title="Existing history",
            data_json='{"notes":"existing private data"}',
        )
        db.add(project)
        db.add(
            AdminAccess(account_id=account.id, enabled=True, secret_cipher="old synthetic cipher")
        )
        db.commit()
        account_id, project_id = account.id, project.id
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "database_path", str(path))
    try:
        database.init_db()
        database.init_db()
        columns = {column["name"] for column in inspect(engine).get_columns("package_reservations")}
        assert {"session_id", "project_id", "response_expires_at"} <= columns
        with factory() as db:
            assert db.get(Account, account_id).password_hash == "old hash"
            assert db.get(AdminAccess, account_id).secret_cipher == "old synthetic cipher"
            assert db.get(Application, project_id).data_json == '{"notes":"existing private data"}'
            assert billing.balance(db, account_id)["available"] == 3
            assert db.execute(text("PRAGMA foreign_key_check")).all() == []
    finally:
        engine.dispose()


def test_scheduled_cleanup_erases_expired_response_cache_and_retains_owned_history(
    store, hosted_client, monkeypatch
):
    from backend import cleanup as scheduled_cleanup

    factory, _account_id, _settings = store
    client, payload, documents, _registration = hosted_client
    result = client.post("/api/package", json=payload).json()
    with factory() as db:
        record = db.query(PackageReservation).filter_by(request_id=payload["request_id"]).one()
        record.response_expires_at = billing._now() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(scheduled_cleanup, "SessionLocal", factory)
    assert scheduled_cleanup.cleanup() == 0
    with factory() as db:
        record = db.query(PackageReservation).filter_by(request_id=payload["request_id"]).one()
        assert record.response_json is None and record.status == "completed"
        assert billing.balance(db, record.account_id)["available"] == 2
    assert client.get("/api/projects/" + result["project_id"]).json()["documents"] == documents


def test_draft_edit_during_generation_is_preserved_and_credit_refunded(
    store, hosted_client, monkeypatch
):
    factory, _account_id, _settings = store
    client, payload, documents, _registration = hosted_client
    initial = client.post(
        "/api/projects",
        json={
            "session_id": payload["session_id"],
            "title": "Draft",
            "profile": payload["profile"],
            "job": payload["job"],
            "documents": None,
        },
    ).json()
    payload.update(project_id=initial["id"], project_revision=initial["revision"])

    def edit_while_generating(*_args, **_kwargs):
        with factory() as db:
            project = db.get(Application, initial["id"])
            data = json.loads(project.data_json)
            data.update(notes="Concurrent private edit", _revision=2)
            project.data_json = json.dumps(data)
            db.commit()
        return LLMResult(json.dumps(documents), "openai", "test")

    monkeypatch.setattr(hosted_ai.Provider, "generate", edit_while_generating)
    result = client.post("/api/package", json=payload)
    assert result.status_code == 409, result.text
    assert result.json()["detail"]["code"] == "PACKAGE_PROJECT_CONFLICT"
    saved = client.get("/api/projects/" + initial["id"]).json()
    assert saved["notes"] == "Concurrent private edit" and saved["documents"] is None
    assert len(client.get("/api/projects").json()) == 1
    assert client.get("/api/billing/balance").json()["available"] == 3


def test_reopened_draft_promotes_after_relogin_with_new_owned_session(store, hosted_client):
    from backend.tests.test_platform import session

    factory, _account_id, _settings = store
    client, payload, documents, registration = hosted_client
    previous_session = payload["session_id"]
    draft = client.post(
        "/api/projects",
        json={
            "session_id": previous_session,
            "title": "Saved draft",
            "profile": payload["profile"],
            "job": payload["job"],
            "documents": None,
        },
    ).json()
    assert client.post("/api/account/logout", json={}).status_code == 200
    assert (
        client.post(
            "/api/account/login",
            json={
                "email": registration["email"],
                "password": "test-long-password-123",
            },
        ).status_code
        == 200
    )
    current_session = session(client)
    assert current_session != previous_session
    payload.update(session_id=current_session, project_id=draft["id"], project_revision=1)
    generated = client.post("/api/package", json=payload)
    assert generated.status_code == 200, generated.text
    assert generated.json()["project_id"] == draft["id"]
    assert generated.json()["project_revision"] == 2
    saved = client.get("/api/projects/" + draft["id"]).json()
    assert saved["session_id"] == current_session and saved["documents"] == documents
    assert len(client.get("/api/projects").json()) == 1
    with factory() as db:
        assert db.get(Application, draft["id"]).session_id == current_session
        record = db.query(PackageReservation).filter_by(request_id=payload["request_id"]).one()
        assert record.session_id == current_session
    assert client.post("/api/package", json=payload).json() == generated.json()


def test_existing_draft_cannot_promote_through_another_accounts_session(hosted_client, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.tests.test_platform import register, session

    owner, payload, _documents, _registration = hosted_client
    draft = owner.post(
        "/api/projects",
        json={
            "session_id": payload["session_id"],
            "title": "Private draft",
            "profile": payload["profile"],
            "job": payload["job"],
            "documents": None,
        },
    ).json()
    stranger = TestClient(app)
    register(stranger)
    payload.update(session_id=session(stranger), project_id=draft["id"], project_revision=1)
    monkeypatch.setattr(
        hosted_ai.Provider, "generate", lambda *_a, **_kw: pytest.fail("Foreign draft called AI")
    )
    refused = stranger.post("/api/package", json=payload)
    assert refused.status_code == 404, refused.text
    assert stranger.get("/api/billing/balance").json()["available"] == 3
    assert stranger.get("/api/projects").json() == []
    assert owner.get("/api/projects/" + draft["id"]).json()["documents"] is None


def test_session_delete_purges_earlier_responses_after_project_moves_sessions(store, hosted_client):
    from backend.routers.platform import PackageRequest
    from backend.tests.test_platform import session

    factory, _account_id, _settings = store
    client, first_payload, _documents, _registration = hosted_client
    first = client.post("/api/package", json=first_payload).json()
    second_payload = {
        **first_payload,
        "request_id": str(uuid4()),
        "session_id": session(client),
        "project_id": first["project_id"],
        "project_revision": first["project_revision"],
    }
    second = client.post("/api/package", json=second_payload)
    assert second.status_code == 200, second.text
    assert second.json()["project_id"] == first["project_id"]
    assert second.json()["project_revision"] == 2
    assert client.delete("/api/session/" + second_payload["session_id"]).status_code == 200
    with factory() as db:
        records = db.query(PackageReservation).order_by(PackageReservation.created_at).all()
        assert len(records) == 2
        for record, payload in zip(records, [first_payload, second_payload], strict=True):
            assert record.project_id is None and record.response_json is None
            assert record.status == "completed"
            with pytest.raises(HTTPException) as deleted:
                billing.reserve_package(
                    db,
                    record.account_id,
                    payload["request_id"],
                    PackageRequest(**payload).model_dump(mode="json", exclude={"request_id"}),
                )
            assert deleted.value.status_code == 410
        assert db.get(Application, first["project_id"]) is None
        assert db.get(Session, first_payload["session_id"]) is not None
        assert billing.balance(db, records[0].account_id)["used"] == 2
        assert billing.balance(db, records[0].account_id)["available"] == 1
