"""Berlin calendar-week free credits, persistent paid credits and fenced fulfillment."""

import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_, text

from backend.config import get_settings
from backend.models import (
    Application,
    CheckoutConsent,
    CreditLedger,
    CreditWallet,
    PackageCreditAllocation,
    PackageReservation,
    PaymentEvent,
    PaymentOrder,
    PaymentWithdrawal,
    Session,
    WeeklyCreditWallet,
)

RESERVATION_MINUTES = 10
RESPONSE_CACHE_HOURS = 24
FREE_TIMEZONE = "Europe/Berlin"


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


def _week(now=None, *, key=None):
    zone = ZoneInfo(FREE_TIMEZONE)
    if key is None:
        now = now or _now()
        utc = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
        local_day = utc.astimezone(zone).date()
        monday = local_day - timedelta(days=local_day.weekday())
    else:
        monday = date.fromisoformat(key)
    start = datetime.combine(monday, time.min, zone).astimezone(UTC).replace(tzinfo=None)
    end = (
        datetime.combine(monday + timedelta(days=7), time.min, zone)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    return monday.isoformat(), start, end


def _sync_wallet(wallet, weekly):
    wallet.available = weekly.free_remaining + weekly.paid_remaining


def _ledger_adjustment(db, account_id, key, delta):
    if delta:
        db.add(
            CreditLedger(
                account_id=account_id,
                entry_key=key,
                kind="welcome" if delta > 0 else "reserve",
                delta=delta,
            )
        )


def _roll_week(db, wallet, weekly):
    key, _, _ = _week()
    # A backward clock adjustment must never grant an already elapsed week again.
    if key > weekly.week_key:
        _ledger_adjustment(
            db, wallet.account_id, f"weekly-expire:{weekly.week_key}", -weekly.free_remaining
        )
        weekly.week_key = key
        weekly.free_total = get_settings().billing_free_packages
        weekly.free_remaining = weekly.free_total
        _ledger_adjustment(db, wallet.account_id, f"weekly-grant:{key}", weekly.free_total)
        _sync_wallet(wallet, weekly)


def _wallet(db, account_id):
    wallet = db.get(CreditWallet, account_id)
    weekly = db.get(WeeklyCreditWallet, account_id)
    key, start, end = _week()
    if weekly is None:
        grant = get_settings().billing_free_packages
        if wallet is None:
            wallet = CreditWallet(account_id=account_id, available=grant, free_total=grant)
            db.add(wallet)
            weekly = WeeklyCreditWallet(
                account_id=account_id,
                paid_remaining=0,
                free_remaining=grant,
                free_total=grant,
                week_key=key,
            )
            _ledger_adjustment(db, account_id, f"weekly-grant:{key}", grant)
        else:
            # The old aggregate spent its one-time free grant before paid credits.
            # Keep every remaining paid credit, and count this week's old requests
            # against the new quota instead of granting a second free allowance.
            active = (
                db.query(PackageReservation)
                .filter(
                    PackageReservation.account_id == account_id,
                    PackageReservation.status.in_(("reserved", "completed")),
                )
                .all()
            )
            active.sort(key=lambda row: row.expires_at - timedelta(minutes=RESERVATION_MINUTES))
            old_free = max(0, wallet.free_total - len(active))
            paid = max(0, wallet.available - old_free)
            current = [
                row
                for row in active
                if start <= row.expires_at - timedelta(minutes=RESERVATION_MINUTES) < end
            ]
            quota_ids = {row.id for row in current[:grant]}
            weekly = WeeklyCreditWallet(
                account_id=account_id,
                paid_remaining=paid,
                free_remaining=max(0, grant - len(current)),
                free_total=grant,
                week_key=key,
            )
            for index, row in enumerate(active):
                if row.status == "reserved":
                    db.add(
                        PackageCreditAllocation(
                            reservation_id=row.id,
                            attempt=row.attempt,
                            funding="free" if index < wallet.free_total else "paid",
                            free_week=key if row.id in quota_ids else None,
                            weekly_debit=row.id in quota_ids,
                        )
                    )
            _ledger_adjustment(
                db,
                account_id,
                "weekly-migration:v1",
                weekly.free_remaining + paid - wallet.available,
            )
        db.add(weekly)
        _sync_wallet(wallet, weekly)
        db.flush()
    _roll_week(db, wallet, weekly)
    return wallet


def _refund(db, reservation, wallet):
    weekly = db.get(WeeklyCreditWallet, reservation.account_id)
    _roll_week(db, wallet, weekly)
    allocation = db.get(PackageCreditAllocation, reservation.id)
    if not allocation or allocation.attempt != reservation.attempt:
        raise error(
            503, "CREDIT_ALLOCATION_UNAVAILABLE", "Credit allocation unavailable; retry later"
        )
    returned = 0
    if allocation.funding == "paid":
        weekly.paid_remaining += 1
        returned += 1
    if allocation.weekly_debit and allocation.free_week == weekly.week_key:
        previous = weekly.free_remaining
        weekly.free_remaining = min(weekly.free_total, previous + 1)
        returned += weekly.free_remaining - previous
    _sync_wallet(wallet, weekly)
    reservation.status = "refunded"
    if returned:
        db.add(
            CreditLedger(
                account_id=reservation.account_id,
                entry_key=f"refund:{reservation.id}:{reservation.attempt}",
                kind="refund",
                delta=returned,
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
    weekly = db.get(WeeklyCreditWallet, account_id)
    _, start, end = _week(key=weekly.week_key)
    return {
        "available": wallet.available,
        "free_remaining": weekly.free_remaining,
        "paid_remaining": weekly.paid_remaining,
        "week_start": start.isoformat() + "Z",
        "week_end": end.isoformat() + "Z",
        "reserved": db.query(PackageReservation)
        .filter_by(account_id=account_id, status="reserved")
        .count(),
        "free_total": weekly.free_total,
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
        weekly = db.get(WeeklyCreditWallet, account_id)
        funding = "free" if weekly.free_remaining else "paid"
        if funding == "free":
            weekly.free_remaining -= 1
        else:
            weekly.paid_remaining -= 1
        _sync_wallet(wallet, weekly)
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
        allocation = db.get(PackageCreditAllocation, record.id)
        if allocation is None:
            allocation = PackageCreditAllocation(reservation_id=record.id)
            db.add(allocation)
        allocation.attempt = record.attempt
        allocation.funding = funding
        allocation.free_week = weekly.week_key if funding == "free" else None
        allocation.weekly_debit = funding == "free"
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


def checkout_consent(
    *,
    terms_version=None,
    terms_accepted=False,
    immediate_performance=False,
    withdrawal_acknowledged=False,
):
    from backend.account_terms import TERMS_VERSION

    if terms_version != TERMS_VERSION or any(
        value is not True
        for value in (
            terms_accepted,
            immediate_performance,
            withdrawal_acknowledged,
        )
    ):
        raise error(
            422,
            "CHECKOUT_CONSENT_REQUIRED",
            "Aktuelle AGB, sofortigen Leistungsbeginn und Widerrufshinweis ausdrücklich bestätigen / confirm the current terms, immediate performance and withdrawal acknowledgement",
        )
    return dict(
        terms_version=TERMS_VERSION,
        withdrawal_version=TERMS_VERSION,
        terms_accepted=True,
        immediate_performance=True,
        withdrawal_acknowledged=True,
    )


def _contract_snapshots(language):
    from backend.services.legal_service import render_text

    if language not in {"de", "en", "sq"}:
        raise error(422, "INVALID_LANGUAGE", "Unsupported document language")
    settings = get_settings()
    operator = {
        "operator_name": settings.operator_name,
        "operator_address": settings.operator_address,
        "operator_email": settings.operator_email,
    }
    try:
        terms = render_text("terms", language, operator, settings.retention_days)
        withdrawal = render_text("withdrawal", language, operator, settings.retention_days)
        if not terms.strip() or not withdrawal.strip() or max(len(terms), len(withdrawal)) > 60000:
            raise ValueError("Contract snapshot unavailable")
        return terms, withdrawal
    except (OSError, ValueError, KeyError):
        raise error(
            503, "CONTRACT_INFORMATION_UNAVAILABLE", "Contract information unavailable; retry later"
        ) from None


def prepare_order(db, account_id, request_id, provider, offer_id, *, language="de", **consent):
    accepted = checkout_consent(**consent)
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
            recorded = db.get(CheckoutConsent, record.id)
            if (
                not recorded
                or recorded.terms_version != accepted["terms_version"]
                or recorded.language != language
            ):
                raise error(
                    409,
                    "IDEMPOTENCY_CONFLICT",
                    "Checkout ID belongs to different or missing consent",
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
        terms, withdrawal = _contract_snapshots(language)
        db.add(
            CheckoutConsent(
                order_id=record.id,
                accepted_at=_now(),
                language=language,
                terms_snapshot=terms,
                withdrawal_snapshot=withdrawal,
                **accepted,
            )
        )
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
            consent = db.get(CheckoutConsent, order.id)
            if not consent:
                raise error(
                    503,
                    "ORDER_CONSENT_UNAVAILABLE",
                    "Original order consent unavailable; contact the operator",
                )
            receipt = _purchase_receipt(db, order, consent)
            db.flush()
            consent.receipt_outbox_id = receipt.id
            wallet = _wallet(db, order.account_id)
            weekly = db.get(WeeklyCreditWallet, order.account_id)
            weekly.paid_remaining += order.credits
            _sync_wallet(wallet, weekly)
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


def _purchase_receipt(db, order, consent):
    from backend.models import Account
    from backend.services.account_mail import queue_receipt

    copy = {
        "de": (
            "Kaufbestätigung – TafolliBoost",
            "Deine einmalige Bestellung ist bezahlt.",
            "Bestellung",
            "Bewerbungsmappen",
            "Gesamtbetrag",
            "Kein Abonnement und keine automatische Verlängerung.",
            "Du hast die AGB angenommen, den sofortigen Leistungsbeginn verlangt und die Widerrufsbelehrung bestätigt. Das beendet dein Widerrufsrecht nicht pauschal beim Kauf. Die vollständigen vereinbarten Informationen stehen unten.",
        ),
        "en": (
            "Purchase confirmation – TafolliBoost",
            "Your one-time order has been paid.",
            "Order",
            "Application packages",
            "Total amount",
            "No subscription or automatic renewal.",
            "You accepted the terms, requested immediate performance and acknowledged the withdrawal information. Buying credits does not automatically end your withdrawal rights. The complete agreed information is included below.",
        ),
        "sq": (
            "Konfirmimi i blerjes – TafolliBoost",
            "Porosia jote me pagesë të vetme është paguar.",
            "Porosia",
            "Dosje aplikimi",
            "Shuma totale",
            "Pa abonim dhe pa rinovim automatik.",
            "Ke pranuar kushtet, ke kërkuar fillimin e menjëhershëm të shërbimit dhe ke konfirmuar informacionin për tërheqjen. Blerja e krediteve nuk e përfundon automatikisht të drejtën e tërheqjes. Informacioni i plotë i pranuar është përfshirë më poshtë.",
        ),
    }[consent.language]
    subject, intro, order_label, credit_label, amount_label, once, acknowledgement = copy
    body = (
        f"{intro}\n\n{order_label}: {order.id}\n{credit_label}: {order.credits}\n"
        f"{amount_label}: {Decimal(order.amount_cents) / 100:.2f} EUR\n"
        f"{once}\n\n{acknowledgement}\nVersion: {consent.terms_version}\n"
        f"UTC: {consent.accepted_at.isoformat()}\n\n"
        f"{consent.terms_snapshot}\n\n{consent.withdrawal_snapshot}"
    )
    return queue_receipt(db, db.get(Account, order.account_id), subject, body, consent.language)


def list_orders(db, account_id):
    result = []
    for order in (
        db.query(PaymentOrder)
        .filter_by(account_id=account_id)
        .order_by(PaymentOrder.created_at.desc())
        .all()
    ):
        withdrawal = db.query(PaymentWithdrawal).filter_by(order_id=order.id).first()
        result.append(
            {
                "id": order.id,
                "credits": order.credits,
                "amount_cents": order.amount_cents,
                "currency": order.currency,
                "provider": order.provider,
                "status": order.status,
                "created_at": order.created_at.isoformat() + "Z",
                "withdrawal_status": withdrawal.status if withdrawal else None,
                "withdrawal_id": withdrawal.id if withdrawal else None,
                "withdrawal_requested_at": withdrawal.requested_at.isoformat() + "Z"
                if withdrawal
                else None,
            }
        )
    return result


def request_withdrawal(db, account, order_id, name, confirmed, *, language="de"):
    from backend.account_models import EmailOutbox
    from backend.services.account_mail import queue_receipt

    if (
        confirmed is not True
        or not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 200
        or re.search(r"[\x00-\x1f\x7f]", name)
    ):
        raise error(
            422,
            "WITHDRAWAL_CONFIRMATION_REQUIRED",
            "Namen angeben und Widerruf ausdrücklich bestätigen / provide your name and confirm withdrawal",
        )
    if language not in {"de", "en", "sq"}:
        raise error(422, "INVALID_LANGUAGE", "Unsupported receipt language")
    with _transaction(db):
        order = db.get(PaymentOrder, str(order_id))
        if not order or order.account_id != account.id:
            raise error(404, "ORDER_NOT_FOUND", "Payment order not found")
        withdrawal = db.query(PaymentWithdrawal).filter_by(order_id=order.id).first()
        if withdrawal is None:
            withdrawal = PaymentWithdrawal(
                order_id=order.id, name=name.strip(), requested_at=_now()
            )
            db.add(withdrawal)
            db.flush()
            subject, text = _withdrawal_receipt(withdrawal, order, language)
            receipt = queue_receipt(db, account, subject, text, language)
            db.flush()
            withdrawal.receipt_outbox_id = receipt.id
        outbox = (
            db.get(EmailOutbox, withdrawal.receipt_outbox_id)
            if withdrawal.receipt_outbox_id
            else None
        )
        return {
            "withdrawal_id": withdrawal.id,
            "order_id": order.id,
            "requested_at": withdrawal.requested_at.isoformat() + "Z",
            "status": withdrawal.status,
            "receipt_status": "queued"
            if outbox and outbox.status in {"pending", "sending"}
            else outbox.status
            if outbox
            else "recorded",
        }


def _withdrawal_receipt(withdrawal, order, language):
    copy = {
        "de": (
            "Eingangsbestätigung deines Widerrufs – TafolliBoost",
            "Hallo",
            "Wir haben deinen Widerruf erhalten.",
            "Bestellung",
            "Angebot",
            "Bewerbungsmappen",
            "Widerrufskennung",
            "Dies bestätigt den Eingang deiner Erklärung. Eine Erstattung oder deren Höhe ist damit noch nicht bestätigt. Der Betreiber prüft die Rückabwicklung und gegebenenfalls bereits erbrachte Leistungen.",
            "Bei Fragen wende dich an",
        ),
        "en": (
            "Confirmation of your withdrawal request – TafolliBoost",
            "Hello",
            "We have received your withdrawal request.",
            "Order",
            "Offer",
            "Application packages",
            "Withdrawal reference",
            "This confirms receipt of your declaration. A refund or its amount has not yet been confirmed. The operator will review the reversal and any services already provided.",
            "For questions contact",
        ),
        "sq": (
            "Konfirmimi i kërkesës për tërheqje – TafolliBoost",
            "Përshëndetje",
            "Kemi marrë kërkesën tënde për tërheqje.",
            "Porosia",
            "Oferta",
            "Dosje aplikimi",
            "Identifikuesi i tërheqjes",
            "Kjo konfirmon marrjen e deklaratës tënde. Rimbursimi ose shuma e tij ende nuk është konfirmuar. Operatori do të shqyrtojë kthimin e pagesës dhe shërbimet e kryera deri tani.",
            "Për pyetje kontakto",
        ),
    }[language]
    subject, greeting, intro, order_label, offer_label, packages, reference, notice, contact = copy
    text = (
        f"{greeting} {withdrawal.name},\n\n{intro}\nUTC: {withdrawal.requested_at.isoformat()}\n"
        f"{order_label}: {order.id}\n{offer_label}: {order.credits} {packages}, {Decimal(order.amount_cents) / 100:.2f} EUR\n"
        f"{reference}: {withdrawal.id}\n\n{notice}\n{contact} {get_settings().operator_email}.\n\nTafolliBoost"
    )
    return subject, text
