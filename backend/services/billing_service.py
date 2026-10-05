"""Persistent lifetime credits, fenced reservations and verified payment fulfillment."""

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, text

from backend.config import get_settings
from backend.models import (
    Application,
    CreditLedger,
    CreditWallet,
    PackageReservation,
    PaymentEvent,
    PaymentOrder,
    Session,
)

RESERVATION_MINUTES = 10
RESPONSE_CACHE_HOURS = 24


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


def error(status, code, message):
    return HTTPException(status, {"code": code, "message": message})


@contextmanager
def _transaction(db):
    # SQLite is the production store. Serialize the read/check/write together,
    # release its lock before network calls, and discard stale identity-map rows.
    db.commit()
    if db.bind.dialect.name != "sqlite":
        raise error(
            503, "BILLING_STORE_UNSUPPORTED", "Billing requires the configured SQLite store"
        )
    db.execute(text("BEGIN IMMEDIATE"))
    db.expire_all()
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def _wallet(db, account_id):
    wallet = db.get(CreditWallet, account_id)
    if wallet is None:
        # Additive, lazy migration: existing accounts get the same three lifetime
        # credits; old demonstrations are not charged retrospectively.
        grant = get_settings().billing_free_packages
        wallet = CreditWallet(account_id=account_id, available=grant, free_total=grant)
        db.add(wallet)
        db.add(
            CreditLedger(account_id=account_id, entry_key="welcome:v1", kind="welcome", delta=grant)
        )
        db.flush()
    return wallet


def _refund(db, reservation, wallet):
    wallet.available += 1
    reservation.status = "refunded"
    db.add(
        CreditLedger(
            account_id=reservation.account_id,
            entry_key=f"refund:{reservation.id}:{reservation.attempt}",
            kind="refund",
            delta=1,
        )
    )


def _expire(db, account_id, wallet):
    # A terminated worker must not retain a person's credit forever. The lease
    # exceeds the bounded provider timeout; attempt fencing protects a new retry.
    for reservation in (
        db.query(PackageReservation)
        .filter(
            PackageReservation.account_id == account_id,
            PackageReservation.status == "reserved",
            PackageReservation.expires_at < _now(),
        )
        .all()
    ):
        _refund(db, reservation, wallet)
    db.flush()
    purge_cached_responses(db, expired_at=_now(), account_id=account_id)


def purge_cached_responses(
    db, *, session_ids=None, project_ids=None, expired_at=None, account_id=None
):
    """Erase document copies in the caller's transaction; retain credit tombstones."""
    query = db.query(PackageReservation).filter(PackageReservation.response_json.is_not(None))
    if account_id is not None:
        query = query.filter(PackageReservation.account_id == account_id)
    scopes = []
    if session_ids:
        scopes.append(PackageReservation.session_id.in_(session_ids))
    if project_ids:
        scopes.append(PackageReservation.project_id.in_(project_ids))
    if expired_at is not None:
        scopes.append(PackageReservation.response_expires_at <= expired_at)
        # Unbounded legacy caches are not retained after this upgrade.
        scopes.append(PackageReservation.response_expires_at.is_(None))
    if not scopes:
        return 0
    return query.filter(or_(*scopes)).update(
        {PackageReservation.response_json: None, PackageReservation.response_expires_at: None},
        synchronize_session="fetch",
    )


def _package_target(db, account_id, session_id, project_id=None, project_revision=None):
    session = db.get(Session, session_id)
    if not session or session.owner_id != account_id:
        raise error(404, "PACKAGE_SESSION_DELETED", "Application session no longer available")
    if project_id is None:
        return None
    project = db.get(Application, str(project_id))
    source_session = db.get(Session, project.session_id) if project else None
    if not source_session or source_session.owner_id != account_id:
        raise error(404, "PACKAGE_PROJECT_DELETED", "Application draft no longer available")
    if json.loads(project.data_json).get("_revision") != project_revision:
        raise error(
            409,
            "PACKAGE_PROJECT_CONFLICT",
            "Diese Bewerbung wurde geändert. Bitte im Verlauf erneut öffnen / reopen this application from history",
        )
    return project


def _balance(db, account_id, wallet):
    return {
        "available": wallet.available,
        "reserved": db.query(PackageReservation)
        .filter_by(account_id=account_id, status="reserved")
        .count(),
        "free_total": wallet.free_total,
        "used": db.query(PackageReservation)
        .filter_by(account_id=account_id, status="completed")
        .count(),
    }


def balance(db, account_id):
    with _transaction(db):
        wallet = _wallet(db, account_id)
        _expire(db, account_id, wallet)
        return _balance(db, account_id, wallet)


@dataclass(frozen=True)
class PackageLease:
    id: str
    attempt: int


def reserve_package(db, account_id, request_id, payload, **target):
    lease, cached = _reserve_package(db, account_id, request_id, payload, **target)
    if isinstance(cached, HTTPException):
        raise cached
    return lease, cached


def _reserve_package(
    db, account_id, request_id, payload, *, session_id=None, project_id=None, project_revision=None
):
    fingerprint = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    with _transaction(db):
        wallet = _wallet(db, account_id)
        _expire(db, account_id, wallet)
        record = (
            db.query(PackageReservation)
            .filter_by(
                account_id=account_id,
                request_id=str(request_id),
            )
            .first()
        )
        if record:
            if record.fingerprint != fingerprint:
                raise error(
                    409, "IDEMPOTENCY_CONFLICT", "Request ID already belongs to different input"
                )
            if record.status == "completed":
                if record.response_json:
                    return None, json.loads(record.response_json)
                # Return the error first so the transaction commits cache expiry
                # rather than rolling that privacy deletion back when raising.
                return None, error(
                    410,
                    "PACKAGE_REPLAY_UNAVAILABLE",
                    "Die gespeicherte Antwort ist gelöscht oder abgelaufen. Vorhandene Mappen stehen im Verlauf / saved response deleted or expired; check application history",
                )
            if record.status == "reserved":
                raise error(
                    409,
                    "PACKAGE_IN_PROGRESS",
                    "Diese Mappe wird bereits erstellt / package in progress",
                )
        if session_id is not None:
            _package_target(db, account_id, session_id, project_id, project_revision)
        if wallet.available < 1:
            raise error(
                402,
                "CREDITS_EXHAUSTED",
                "Kein Bewerbungs-Guthaben mehr / no package credits remaining",
            )
        wallet.available -= 1
        if record is None:
            record = PackageReservation(
                account_id=account_id,
                session_id=session_id,
                request_id=str(request_id),
                fingerprint=fingerprint,
                status="reserved",
                attempt=1,
                expires_at=_now() + timedelta(minutes=RESERVATION_MINUTES),
            )
            db.add(record)
            db.flush()
        else:
            record.attempt += 1
            record.status = "reserved"
            record.expires_at = _now() + timedelta(minutes=RESERVATION_MINUTES)
            record.session_id = session_id
        db.add(
            CreditLedger(
                account_id=account_id,
                entry_key=f"reserve:{record.id}:{record.attempt}",
                kind="reserve",
                delta=-1,
            )
        )
        return PackageLease(record.id, record.attempt), None


def complete_package(
    db,
    account_id,
    lease,
    response,
    *,
    session_id=None,
    project_id=None,
    project_revision=None,
    project_data=None,
):
    with _transaction(db):
        record = db.get(PackageReservation, lease.id)
        if (
            not record
            or record.account_id != account_id
            or record.attempt != lease.attempt
            or record.status != "reserved"
        ):
            raise error(
                409, "PACKAGE_RESERVATION_EXPIRED", "Package reservation expired; retry safely"
            )
        if session_id is not None:
            project = _package_target(db, account_id, session_id, project_id, project_revision)
            previous = json.loads(project.data_json) if project else {}
            now = _now()
            data = {
                "design": "modern",
                "notes": "",
                "photo": None,
                **previous,
                **project_data,
                "_created_at": previous.get("_created_at", now.isoformat() + "Z"),
                "_generated_at": now.isoformat() + "Z",
                "_revision": previous.get("_revision", 0) + 1,
            }
            if previous.get("title"):
                data["title"] = previous["title"]
            if project is None:
                project = Application(session_id=session_id)
                db.add(project)
            # A draft reopened after login may belong to an older session of
            # this same account. Align its persisted/session metadata with the
            # current owned session without requiring its former access token.
            project.session_id = session_id
            project.title, project.status = data["title"], data["status"]
            project.data_json = json.dumps(data, ensure_ascii=False)
            project.updated_at = now
            db.flush()
            record.session_id, record.project_id = session_id, project.id
            response["project_id"] = project.id
            response["project_revision"] = data["_revision"]
            response["revision"] = data["_revision"]
        record.response_json = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
        record.response_expires_at = _now() + timedelta(hours=RESPONSE_CACHE_HOURS)
        record.status = "completed"
    return response


def refund_package(db, account_id, lease):
    with _transaction(db):
        record = db.get(PackageReservation, lease.id)
        if (
            record
            and record.account_id == account_id
            and record.attempt == lease.attempt
            and record.status == "reserved"
        ):
            _refund(db, record, _wallet(db, account_id))


def offers():
    s = get_settings()
    return [
        {"id": "single", "credits": 1, "amount_cents": s.billing_single_cents},
        {"id": "bundle10", "credits": 10, "amount_cents": s.billing_bundle10_cents},
    ]


def prepare_order(db, account_id, request_id, provider, offer_id):
    offer = next((item for item in offers() if item["id"] == offer_id), None)
    if not offer:
        raise error(422, "INVALID_OFFER", "Unknown offer")
    with _transaction(db):
        record = (
            db.query(PaymentOrder)
            .filter_by(account_id=account_id, request_id=str(request_id))
            .first()
        )
        if record:
            if record.provider != provider or record.offer_id != offer_id:
                raise error(
                    409, "IDEMPOTENCY_CONFLICT", "Checkout ID already belongs to a different offer"
                )
            return record.id
        record = PaymentOrder(
            account_id=account_id,
            request_id=str(request_id),
            provider=provider,
            offer_id=offer_id,
            amount_cents=offer["amount_cents"],
            credits=offer["credits"],
            currency="EUR",
        )
        db.add(record)
        db.flush()
        return record.id


def save_checkout(db, order_id, provider_order_id, url):
    with _transaction(db):
        order = db.get(PaymentOrder, order_id)
        if order.provider_order_id and order.provider_order_id != provider_order_id:
            raise error(409, "CHECKOUT_CONFLICT", "Provider returned a different checkout")
        order.provider_order_id, order.checkout_url = provider_order_id, url


def credit_paid_order(db, order_id, provider, event_id):
    with _transaction(db):
        event = db.get(PaymentEvent, (provider, event_id))
        if event:
            if event.order_id != order_id:
                raise error(409, "PAYMENT_EVENT_CONFLICT", "Payment event belongs to another order")
            return False
        order = db.get(PaymentOrder, order_id)
        if not order or order.provider != provider or not order.provider_order_id:
            raise error(400, "PAYMENT_ORDER_MISMATCH", "Unknown payment order")
        if order.status != "paid":
            wallet = _wallet(db, order.account_id)
            wallet.available += order.credits
            db.add(
                CreditLedger(
                    account_id=order.account_id,
                    entry_key=f"purchase:{order.id}",
                    kind="purchase",
                    delta=order.credits,
                )
            )
            order.status = "paid"
        db.add(PaymentEvent(provider=provider, event_id=event_id, order_id=order.id))
        return True
