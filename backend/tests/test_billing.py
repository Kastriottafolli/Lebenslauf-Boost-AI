"""Credits remain bounded under concurrent retries; money cannot be browser-asserted."""

import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from backend.account_models import AccountSecurity, EmailOutbox
from backend.account_terms import PRIVACY_VERSION, TERMS_VERSION
from backend.config import get_settings
from backend.database import Base
from backend.llm.base import LLMResult
from backend.models import (
    Account,
    Application,
    CheckoutConsent,
    CreditLedger,
    CreditWallet,
    PackageCreditAllocation,
    PackageReservation,
    PaymentOrder,
    PaymentWithdrawal,
    Session,
    WeeklyCreditWallet,
)
from backend.services import account_mail, hosted_ai
from backend.services import billing_service as billing
from backend.services import payment_service as payments

CONSENT = {
    "terms_version": TERMS_VERSION,
    "terms_accepted": True,
    "immediate_performance": True,
    "withdrawal_acknowledged": True,
}


def counts(value):
    return {key: value[key] for key in ("available", "reserved", "free_total", "used")}


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
    monkeypatch.setattr(settings, "mail_key_file", str(tmp_path / "mail-test.key"))
    monkeypatch.setattr(account_mail, "ready", lambda: True)
    monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 6, 12))
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
        db.add(
            AccountSecurity(
                account_id=account_id,
                verified_at=billing._now(),
                terms_version=TERMS_VERSION,
                privacy_version=PRIVACY_VERSION,
            )
        )
        db.commit()
    yield factory, account_id, settings
    engine.dispose()


def test_free_quota_is_per_berlin_calendar_week_without_rollover(store, monkeypatch):
    factory, account_id, settings = store
    with factory() as db:
        assert counts(billing.balance(db, account_id)) == {
            "available": 3,
            "reserved": 0,
            "free_total": 3,
            "used": 0,
        }
        lease, _ = billing.reserve_package(db, account_id, uuid4(), {})
        billing.complete_package(db, account_id, lease, {"done": True})
        assert billing.balance(db, account_id)["free_remaining"] == 2
        monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 11, 21, 59, 59))
        assert billing.balance(db, account_id)["free_remaining"] == 2
        monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 11, 22))
        renewed = billing.balance(db, account_id)
        assert renewed["free_remaining"] == renewed["available"] == 3
        assert renewed["paid_remaining"] == 0
        assert renewed["week_start"] == "2026-10-11T22:00:00Z"
        assert renewed["week_end"] == "2026-10-18T22:00:00Z"
        assert db.query(CreditLedger).filter_by(account_id=account_id, kind="welcome").count() == 2


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
        assert counts(billing.balance(db, account_id)) == {
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
                payments.checkout(db, account_id, uuid4(), "stripe", "single", **CONSENT)
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
                json={"id": f"cs_test_order_{len(calls)}", "url": "https://checkout.stripe.com/order"},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(payments, "_client", Network)
    with factory() as db:
        request_id = uuid4()
        first = payments.checkout(db, account_id, request_id, "stripe", "single", **CONSENT)
        monkeypatch.setattr(settings, "billing_single_cents", 300)
        assert payments.checkout(db, account_id, request_id, "stripe", "single", **CONSENT) == first
        assert len(calls) == 1
        assert calls[0]["data"]["line_items[0][price_data][unit_amount]"] == "199"
        assert "payment_method_types[0]" not in calls[0]["data"]
        assert calls[0]["headers"]["Idempotency-Key"] == first["order_id"]
        assert billing.balance(db, account_id)["available"] == 3
        with pytest.raises(HTTPException) as conflict:
            payments.checkout(db, account_id, request_id, "stripe", "bundle10", **CONSENT)
        assert conflict.value.detail["code"] == "IDEMPOTENCY_CONFLICT"
        monkeypatch.setattr(settings, "billing_single_cents", 199)
        combined = payments.checkout(db, account_id, uuid4(), "stripe", "s1b1", **CONSENT)
        assert calls[-1]["data"]["line_items[0][price_data][unit_amount]"] == "1198"
        combined_order = db.get(PaymentOrder, combined["order_id"])
        assert (combined_order.offer_id, combined_order.amount_cents, combined_order.credits) == (
            "s1b1", 1198, 11
        )


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


def test_restricted_stripe_key_is_accepted_only_for_its_mode(store, monkeypatch):
    _factory, _account_id, settings = store
    monkeypatch.setattr(settings, "billing_payments_enabled", True)
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_synthetic")

    monkeypatch.setattr(settings, "billing_environment", "live")
    monkeypatch.setattr(settings, "stripe_secret_key", "rk_live_synthetic")
    assert payments.providers()["stripe"] is True
    assert payments.pricing()["environment"] == "live"

    monkeypatch.setattr(settings, "billing_environment", "sandbox")
    assert payments.providers()["stripe"] is False
    assert payments.pricing()["environment"] == "sandbox"

    monkeypatch.setattr(settings, "stripe_secret_key", "rk_test_synthetic")
    assert payments.providers()["stripe"] is True


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
        order_id = billing.prepare_order(db, account_id, uuid4(), "stripe", "bundle10", **CONSENT)
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
        order_id = billing.prepare_order(db, account_id, uuid4(), "paypal", "single", **CONSENT)
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
        billing.prepare_order(db, account_id, uuid4(), "stripe", "single", **CONSENT)
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
        assert client.get("/api/billing/pricing").json()["free_period"] == "calendar_week"
        assert client.get("/api/billing/pricing").json()["environment"] == "sandbox"
        assert client.get("/api/billing/balance").status_code == 401
        for provider in ("stripe", "paypal"):
            assert (
                client.post(f"/api/billing/webhooks/{provider}", content=b"{}").status_code == 503
            )
        register(client)
        sid = session(client)
        assert client.get("/api/billing/balance").json()["available"] == 3
        checkout = {
            "offer_id": "single",
            "provider": "stripe",
            "request_id": str(uuid4()),
            **CONSENT,
        }
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
        "weekly_credit_wallets",
        "package_credit_allocations",
        "checkout_consents",
        "payment_withdrawals",
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
        record.response_expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
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


@pytest.mark.parametrize(
    ("stamp", "key", "start", "end", "hours"),
    [
        (
            datetime(2026, 3, 23, 0),
            "2026-03-23",
            datetime(2026, 3, 22, 23),
            datetime(2026, 3, 29, 22),
            167,
        ),
        (
            datetime(2026, 10, 19, 0),
            "2026-10-19",
            datetime(2026, 10, 18, 22),
            datetime(2026, 10, 25, 23),
            169,
        ),
    ],
)
def test_berlin_week_boundaries_follow_daylight_saving(stamp, key, start, end, hours):
    actual_key, actual_start, actual_end = billing._week(stamp.replace(tzinfo=UTC))
    assert (actual_key, actual_start, actual_end) == (key, start, end)
    assert (actual_end - actual_start).total_seconds() == hours * 3600
    assert billing._week(end - timedelta(microseconds=1))[0] == key
    assert billing._week(end)[0] != key


def _paid_credits(db, account_id, offer="bundle10"):
    order_id = billing.prepare_order(db, account_id, uuid4(), "stripe", offer, **CONSENT)
    billing.save_checkout(
        db, order_id, "cs_" + order_id.replace("-", ""), "https://checkout.stripe.com/test"
    )
    billing.credit_paid_order(db, order_id, "stripe", "evt_" + order_id)
    return order_id


def test_weekly_free_is_used_before_paid_and_paid_never_expires(store, monkeypatch):
    factory, account_id, _settings = store
    with factory() as db:
        _paid_credits(db, account_id)
        for index in range(4):
            lease, _ = billing.reserve_package(db, account_id, uuid4(), {"index": index})
            allocation = db.get(PackageCreditAllocation, lease.id)
            assert allocation.funding == ("free" if index < 3 else "paid")
            assert allocation.weekly_debit is (index < 3)
            billing.complete_package(db, account_id, lease, {"done": True})
        current = billing.balance(db, account_id)
        assert (current["free_remaining"], current["paid_remaining"], current["available"]) == (
            0,
            9,
            9,
        )
        monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 12, 12))
        renewed = billing.balance(db, account_id)
        assert (renewed["free_remaining"], renewed["paid_remaining"], renewed["available"]) == (
            3,
            9,
            12,
        )
        assert sum(row.delta for row in db.query(CreditLedger).all()) == renewed["available"]


def test_pending_free_refund_after_week_change_does_not_roll_over(store, monkeypatch):
    factory, account_id, _settings = store
    monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 11, 21, 59))
    with factory() as db:
        key = uuid4()
        old, _ = billing.reserve_package(db, account_id, key, {})
        monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 11, 22))
        assert billing.balance(db, account_id)["free_remaining"] == 3
        billing.refund_package(db, account_id, old)
        billing.refund_package(db, account_id, old)
        assert billing.balance(db, account_id)["available"] == 3
        retry, _ = billing.reserve_package(db, account_id, key, {})
        assert retry.attempt == old.attempt + 1
        billing.refund_package(db, account_id, old)
        assert billing.balance(db, account_id)["free_remaining"] == 2
        billing.complete_package(db, account_id, retry, {"done": True})
        assert billing.balance(db, account_id)["used"] == 1


def test_pending_paid_refund_after_week_change_returns_paid_credit(store, monkeypatch):
    factory, account_id, _settings = store
    monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 11, 21, 59))
    with factory() as db:
        _paid_credits(db, account_id, "single")
        for _ in range(3):
            lease, _ = billing.reserve_package(db, account_id, uuid4(), {})
            billing.complete_package(db, account_id, lease, {"done": True})
        old, _ = billing.reserve_package(db, account_id, uuid4(), {})
        assert db.get(PackageCreditAllocation, old.id).funding == "paid"
        monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 11, 22, 10))
        expired = billing.balance(db, account_id)
        assert (expired["free_remaining"], expired["paid_remaining"], expired["available"]) == (
            3,
            1,
            4,
        )
        billing.refund_package(db, account_id, old)
        assert billing.balance(db, account_id)["available"] == 4


def _legacy_reservation(account_id, stamp, *, status="completed"):
    return PackageReservation(
        account_id=account_id,
        request_id=str(uuid4()),
        fingerprint="legacy",
        status=status,
        attempt=1,
        created_at=stamp,
        expires_at=stamp + timedelta(minutes=billing.RESERVATION_MINUTES),
    )


def test_lifetime_migration_preserves_paid_and_counts_current_week_activity(store):
    factory, account_id, _settings = store
    with factory() as db:
        db.add(CreditWallet(account_id=account_id, available=5, free_total=3))
        db.add(CreditLedger(account_id=account_id, entry_key="welcome:v1", kind="welcome", delta=3))
        db.add(
            CreditLedger(
                account_id=account_id, entry_key="legacy-purchase", kind="purchase", delta=7
            )
        )
        for index in range(5):
            stamp = datetime(2026, 9, 30, 12) if index < 3 else datetime(2026, 10, 6, 10 + index)
            db.add(_legacy_reservation(account_id, stamp))
            db.add(
                CreditLedger(
                    account_id=account_id,
                    entry_key=f"legacy-reserve:{index}",
                    kind="reserve",
                    delta=-1,
                )
            )
        db.commit()
        migrated = billing.balance(db, account_id)
        assert (migrated["free_remaining"], migrated["paid_remaining"], migrated["available"]) == (
            1,
            5,
            6,
        )
        assert migrated["used"] == 5
        assert billing.balance(db, account_id) == migrated
        assert db.query(WeeklyCreditWallet).count() == 1
        assert sum(row.delta for row in db.query(CreditLedger).all()) == 6


def test_legacy_pending_paid_refund_restores_paid_and_its_migration_quota(store):
    factory, account_id, _settings = store
    with factory() as db:
        db.add(CreditWallet(account_id=account_id, available=4, free_total=3))
        for _ in range(3):
            db.add(_legacy_reservation(account_id, datetime(2026, 9, 30, 12)))
        pending = _legacy_reservation(account_id, datetime(2026, 10, 6, 11, 59), status="reserved")
        db.add(pending)
        db.commit()
        initial = billing.balance(db, account_id)
        assert (initial["free_remaining"], initial["paid_remaining"]) == (2, 4)
        allocation = db.get(PackageCreditAllocation, pending.id)
        assert allocation.funding == "paid" and allocation.weekly_debit
        billing.refund_package(db, account_id, billing.PackageLease(pending.id, pending.attempt))
        refunded = billing.balance(db, account_id)
        assert (refunded["free_remaining"], refunded["paid_remaining"]) == (3, 5)


def test_parallel_week_renewal_grants_once(store, monkeypatch):
    factory, account_id, _settings = store
    with factory() as db:
        billing.balance(db, account_id)
    monkeypatch.setattr(billing, "_now", lambda: datetime(2026, 10, 12, 12))

    def lookup(_):
        with factory() as db:
            return billing.balance(db, account_id)["available"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(lookup, range(10))) == [3] * 10
    with factory() as db:
        assert db.query(CreditLedger).filter_by(entry_key="weekly-grant:2026-10-12").count() == 1


@pytest.mark.parametrize(
    "changed",
    [
        {"terms_version": "old"},
        {"terms_accepted": False},
        {"immediate_performance": False},
        {"withdrawal_acknowledged": False},
        {"terms_accepted": 1},
    ],
)
def test_checkout_requires_explicit_current_order_consent_before_calls(store, monkeypatch, changed):
    factory, account_id, settings = store
    _stripe_setup(settings, monkeypatch)
    monkeypatch.setattr(
        payments, "_client", lambda: pytest.fail("Rejected consent made payment call")
    )
    with factory() as db:
        with pytest.raises(HTTPException) as denied:
            payments.checkout(db, account_id, uuid4(), "stripe", "single", **{**CONSENT, **changed})
        assert denied.value.status_code == 422
        assert denied.value.detail["code"] == "CHECKOUT_CONSENT_REQUIRED"
        assert db.query(PaymentOrder).count() == 0


def test_checkout_consent_is_order_specific_and_idempotently_recorded(store):
    factory, account_id, _settings = store
    with factory() as db:
        key = uuid4()
        order_id = billing.prepare_order(db, account_id, key, "stripe", "single", **CONSENT)
        original = db.get(CheckoutConsent, order_id)
        stamp = original.accepted_at
        assert original.terms_version == original.withdrawal_version == TERMS_VERSION
        assert (
            original.terms_accepted
            and original.immediate_performance
            and original.withdrawal_acknowledged
        )
        assert billing.prepare_order(db, account_id, key, "stripe", "single", **CONSENT) == order_id
        assert db.query(CheckoutConsent).count() == 1
        assert db.get(CheckoutConsent, order_id).accepted_at == stamp


def test_checkout_requires_account_terms_and_mail_readiness(store, monkeypatch):
    factory, account_id, settings = store
    _stripe_setup(settings, monkeypatch)
    with factory() as db:
        security = db.get(AccountSecurity, account_id)
        security.terms_version = None
        db.commit()
        with pytest.raises(HTTPException) as denied:
            payments.checkout(db, account_id, uuid4(), "stripe", "single", **CONSENT)
        assert denied.value.status_code == 403
        assert denied.value.detail["code"] == "TERMS_ACCEPTANCE_REQUIRED"
        monkeypatch.setattr(account_mail, "ready", lambda: False)
        assert payments.pricing()["payments_enabled"] is False
        with pytest.raises(HTTPException) as disabled:
            payments.checkout(db, account_id, uuid4(), "stripe", "single", **CONSENT)
        assert disabled.value.detail["code"] == "PAYMENTS_UNAVAILABLE"


def test_withdrawal_is_owned_confirmed_and_receipted_once(store):
    factory, account_id, _settings = store
    with factory() as db:
        order_id = billing.prepare_order(db, account_id, uuid4(), "stripe", "single", **CONSENT)
        account = db.get(Account, account_id)
        with pytest.raises(HTTPException) as unconfirmed:
            billing.request_withdrawal(db, account, order_id, "Test Person", False)
        assert unconfirmed.value.status_code == 422
        assert db.query(PaymentWithdrawal).count() == 0
        first = billing.request_withdrawal(db, account, order_id, "Test Person", True)
        assert first["status"] == "requested" and first["receipt_status"] == "queued"
        replay = billing.request_withdrawal(db, account, order_id, "Different name", True)
        assert replay == first
        assert db.query(PaymentWithdrawal).count() == db.query(EmailOutbox).count() == 1
        stored = db.query(PaymentWithdrawal).one()
        assert stored.name == "Test Person" and stored.receipt_outbox_id
        receipt = db.query(EmailOutbox).one()
        assert receipt.recipient == account.email and receipt.purpose == "receipt"
        payload = json.loads(account_mail.cipher().decrypt(receipt.payload_cipher.encode()))
        assert order_id in payload["text"] and stored.id in payload["text"]
        assert "Erstattung" in payload["text"] and "Test Person" in payload["text"]
        assert billing.list_orders(db, account_id)[0]["withdrawal_status"] == "requested"
        stranger = Account(
            email="stranger@example.invalid", password_hash="synthetic", recovery_hash="synthetic"
        )
        db.add(stranger)
        db.commit()
        assert billing.list_orders(db, stranger.id) == []
        with pytest.raises(HTTPException) as denied:
            billing.request_withdrawal(db, stranger, order_id, "Another Person", True)
        assert denied.value.status_code == 404
        assert db.query(PaymentWithdrawal).count() == 1


def test_withdrawal_receipt_queue_failure_rolls_back_request(store, monkeypatch):
    factory, account_id, _settings = store

    def unavailable(*_args, **_kwargs):
        raise HTTPException(503, {"code": "MAIL_UNAVAILABLE", "message": "Synthetic unavailable"})

    monkeypatch.setattr(account_mail, "queue_receipt", unavailable)
    with factory() as db:
        order_id = billing.prepare_order(db, account_id, uuid4(), "stripe", "single", **CONSENT)
        with pytest.raises(HTTPException) as denied:
            billing.request_withdrawal(
                db, db.get(Account, account_id), order_id, "Test Person", True
            )
        assert denied.value.status_code == 503
        assert db.query(PaymentWithdrawal).count() == db.query(EmailOutbox).count() == 0


@pytest.mark.parametrize("language", ["de", "en", "sq"])
def test_paid_confirmation_contains_frozen_contract_and_credits_exactly_once(
    store, monkeypatch, language
):
    from backend.services import legal_service

    factory, account_id, _settings = store
    with factory() as db:
        order_id = billing.prepare_order(
            db, account_id, uuid4(), "stripe", "single", language=language, **CONSENT
        )
        consent = db.get(CheckoutConsent, order_id)
        terms, withdrawal = consent.terms_snapshot, consent.withdrawal_snapshot
        assert terms == legal_service.render_text(
            "terms",
            language,
            {
                "operator_name": get_settings().operator_name,
                "operator_address": get_settings().operator_address,
                "operator_email": get_settings().operator_email,
            },
            get_settings().retention_days,
        )
        assert withdrawal and consent.language == language
        monkeypatch.setattr(legal_service, "render_text", lambda *_a, **_kw: "Changed future terms")
        billing.save_checkout(
            db, order_id, "cs_" + order_id.replace("-", ""), "https://checkout.stripe.com/test"
        )
        assert billing.credit_paid_order(db, order_id, "stripe", "evt_" + order_id)
        assert not billing.credit_paid_order(db, order_id, "stripe", "evt_" + order_id)
        assert billing.credit_paid_order(db, order_id, "stripe", "evt_second_" + order_id)
        assert db.query(EmailOutbox).count() == 1
        stored = db.get(CheckoutConsent, order_id)
        assert (stored.terms_snapshot, stored.withdrawal_snapshot) == (terms, withdrawal)
        assert stored.receipt_outbox_id
        message = db.get(EmailOutbox, stored.receipt_outbox_id)
        payload = json.loads(account_mail.cipher().decrypt(message.payload_cipher.encode()))
        assert payload["language"] == language
        assert terms in payload["text"] and withdrawal in payload["text"]
        assert order_id in payload["text"] and "1.99 EUR" in payload["text"]
        assert "Changed future terms" not in payload["text"]
        assert billing.balance(db, account_id)["paid_remaining"] == 1
        assert db.query(CreditLedger).filter_by(kind="purchase").count() == 1


def test_paid_confirmation_queue_failure_rolls_back_credit_and_event(store, monkeypatch):
    factory, account_id, _settings = store

    def unavailable(*_a, **_kw):
        raise HTTPException(503, {"code": "MAIL_UNAVAILABLE"})

    with factory() as db:
        order_id = billing.prepare_order(db, account_id, uuid4(), "stripe", "single", **CONSENT)
        billing.save_checkout(db, order_id, "cs_test", "https://checkout.stripe.com/test")
        monkeypatch.setattr(account_mail, "queue_receipt", unavailable)
        with pytest.raises(HTTPException):
            billing.credit_paid_order(db, order_id, "stripe", "evt_test")
        assert db.get(PaymentOrder, order_id).status == "pending"
        assert db.get(CheckoutConsent, order_id).receipt_outbox_id is None
        assert db.query(CreditLedger).filter_by(kind="purchase").count() == 0
        assert db.query(EmailOutbox).count() == 0
        assert billing.balance(db, account_id)["paid_remaining"] == 0


@pytest.mark.parametrize(
    "language, word", [("de", "Widerruf"), ("en", "withdrawal"), ("sq", "tërheq")]
)
def test_withdrawal_receipt_is_localized_without_refund_promise(store, language, word):
    factory, account_id, _settings = store
    with factory() as db:
        order_id = billing.prepare_order(
            db, account_id, uuid4(), "stripe", "single", language=language, **CONSENT
        )
        result = billing.request_withdrawal(
            db, db.get(Account, account_id), order_id, "Test Person", True, language=language
        )
        assert result["status"] == "requested"
        message = db.query(EmailOutbox).one()
        payload = json.loads(account_mail.cipher().decrypt(message.payload_cipher.encode()))
        assert payload["language"] == language and word in payload["subject"]
        assert "1.99 EUR" in payload["text"] and order_id in payload["text"]
        assert db.get(PaymentOrder, order_id).status == "pending"
