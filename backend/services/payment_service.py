"""Inactive by default: hosted web checkout and authenticated webhook fulfillment.

No card details pass through the application. Returning from checkout is never
proof of payment. Provider calls use fixed origins and private server settings.
"""

import hashlib
import hmac
import json
import re
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlparse

import httpx

from backend.config import get_settings
from backend.models import PaymentOrder
from backend.services import billing_service as billing

MAX_WEBHOOK_BYTES = 1024 * 1024


def _site():
    value = get_settings().site_url.rstrip("/")
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return ""
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        return ""
    return value


def providers():
    from backend.services.account_mail import ready as mail_ready

    s = get_settings()
    active = s.billing_payments_enabled and bool(_site()) and mail_ready()
    prefix = "sk_live_" if s.billing_environment == "live" else "sk_test_"
    restricted_prefix = prefix.replace("sk_", "rk_", 1)
    return {
        "stripe": bool(
            active
            and s.stripe_secret_key.startswith((prefix, restricted_prefix))
            and s.stripe_webhook_secret.startswith("whsec_")
        ),
        "paypal": bool(
            active
            and s.paypal_client_id.strip()
            and s.paypal_client_secret.strip()
            and s.paypal_webhook_id.strip()
            and s.paypal_merchant_id.strip()
        ),
    }


def require(provider):
    if not providers().get(provider):
        raise billing.error(
            503,
            "PAYMENTS_UNAVAILABLE",
            "Zahlungen sind noch nicht freigeschaltet / payments not enabled",
        )


def pricing():
    from backend.account_terms import TERMS_VERSION

    enabled = providers()
    return {
        "currency": "EUR",
        "free_packages": get_settings().billing_free_packages,
        "free_period": "calendar_week",
        "free_timezone": billing.FREE_TIMEZONE,
        "terms_version": TERMS_VERSION,
        "withdrawal_version": TERMS_VERSION,
        "offers": billing.offers(),
        "payments_enabled": any(enabled.values()),
        "providers": enabled,
    }


def _client():
    return httpx.Client(
        timeout=httpx.Timeout(30, connect=10), follow_redirects=False, trust_env=False
    )


def _json(response):
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid provider response")
    return data


def _paypal_base():
    return (
        "https://api-m.paypal.com"
        if get_settings().billing_environment == "live"
        else "https://api-m.sandbox.paypal.com"
    )


def _paypal_token(client):
    s = get_settings()
    data = _json(
        client.post(
            _paypal_base() + "/v1/oauth2/token",
            auth=(s.paypal_client_id, s.paypal_client_secret),
            data={"grant_type": "client_credentials"},
        )
    )
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Missing payment access token")
    return token


def _redirect(provider, url):
    parsed = urlparse(url)
    expected = (
        {"checkout.stripe.com"}
        if provider == "stripe"
        else {"www.paypal.com"}
        if get_settings().billing_environment == "live"
        else {"www.sandbox.paypal.com"}
    )
    if (
        parsed.scheme != "https"
        or parsed.hostname not in expected
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Unexpected payment redirect")
    return url


def _checkout_response(order):
    return {
        "order_id": order.id,
        "provider": order.provider,
        "checkout_url": _redirect(order.provider, order.checkout_url),
        "status": order.status,
    }


def checkout(db, account_id, request_id, provider, offer_id, *, language="de", **consent):
    from backend.account_terms import require_current_terms
    from backend.models import Account

    require(provider)
    require_current_terms(db, db.get(Account, account_id))
    order_id = billing.prepare_order(
        db, account_id, request_id, provider, offer_id, language=language, **consent
    )
    order = db.get(PaymentOrder, order_id)
    if order.checkout_url:
        return _checkout_response(order)
    return_url = _site() + "/?" + urlencode({"payment": "return", "order": order.id})
    cancel_url = _site() + "/?" + urlencode({"payment": "cancel", "order": order.id})
    try:
        with _client() as client:
            if provider == "stripe":
                data = _json(
                    client.post(
                        "https://api.stripe.com/v1/checkout/sessions",
                        headers={
                            "Authorization": f"Bearer {get_settings().stripe_secret_key}",
                            "Idempotency-Key": order.id,
                        },
                        data={
                            "mode": "payment",
                            "payment_method_types[0]": "card",
                            "success_url": return_url,
                            "cancel_url": cancel_url,
                            "client_reference_id": order.id,
                            "metadata[order_id]": order.id,
                            "line_items[0][quantity]": "1",
                            "line_items[0][price_data][currency]": "eur",
                            "line_items[0][price_data][unit_amount]": str(order.amount_cents),
                            "line_items[0][price_data][product_data][name]": f"TafolliBoost – {order.credits} Bewerbungsmappen",
                        },
                    )
                )
                provider_id, url = data.get("id"), data.get("url")
            else:
                token = _paypal_token(client)
                data = _json(
                    client.post(
                        _paypal_base() + "/v2/checkout/orders",
                        headers={"Authorization": f"Bearer {token}", "PayPal-Request-Id": order.id},
                        json={
                            "intent": "CAPTURE",
                            "purchase_units": [
                                {
                                    "reference_id": order.id,
                                    "custom_id": order.id,
                                    "payee": {"merchant_id": get_settings().paypal_merchant_id},
                                    "amount": {
                                        "currency_code": "EUR",
                                        "value": f"{Decimal(order.amount_cents) / 100:.2f}",
                                    },
                                }
                            ],
                            "payment_source": {
                                "paypal": {
                                    "experience_context": {
                                        "return_url": return_url,
                                        "cancel_url": cancel_url,
                                        "user_action": "PAY_NOW",
                                        "shipping_preference": "NO_SHIPPING",
                                    }
                                }
                            },
                        },
                    )
                )
                provider_id = data.get("id")
                url = next(
                    (
                        link.get("href")
                        for link in data.get("links", [])
                        if link.get("rel") in {"approve", "payer-action"}
                    ),
                    None,
                )
            if not isinstance(provider_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{1,200}", provider_id
            ):
                raise ValueError("Invalid payment order")
            if not isinstance(url, str):
                raise ValueError("Missing checkout URL")
            url = _redirect(provider, url)
        billing.save_checkout(db, order.id, provider_id, url)
        return _checkout_response(db.get(PaymentOrder, order.id))
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise billing.error(
            502,
            "CHECKOUT_UNAVAILABLE",
            "Zahlungsdienst gerade nicht verfügbar / checkout unavailable",
        ) from None


def capture_paypal(db, account_id, order_id):
    require("paypal")
    order = db.get(PaymentOrder, order_id)
    if (
        not order
        or order.account_id != account_id
        or order.provider != "paypal"
        or not order.provider_order_id
    ):
        raise billing.error(404, "ORDER_NOT_FOUND", "Payment order not found")
    if order.status == "paid":
        return {"order_id": order.id, "status": "paid"}
    try:
        with _client() as client:
            token = _paypal_token(client)
            _json(
                client.post(
                    _paypal_base() + f"/v2/checkout/orders/{order.provider_order_id}/capture",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "PayPal-Request-Id": f"capture-{order.id}",
                    },
                    json={},
                )
            )
    except (httpx.HTTPError, ValueError, TypeError):
        raise billing.error(502, "CAPTURE_UNAVAILABLE", "Payment capture unavailable") from None
    # The verified capture webhook, not this browser-triggered response, credits the wallet.
    return {"order_id": order.id, "status": "pending"}


def _event(raw):
    if len(raw) > MAX_WEBHOOK_BYTES:
        raise billing.error(413, "WEBHOOK_TOO_LARGE", "Webhook body too large")
    try:
        event = json.loads(raw)
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("id"), str)
            or not 1 <= len(event["id"]) <= 200
        ):
            raise ValueError()
        return event
    except (ValueError, UnicodeDecodeError):
        raise billing.error(400, "INVALID_WEBHOOK", "Invalid webhook payload") from None


def verify_stripe(raw, signature):
    require("stripe")
    if len(raw) > MAX_WEBHOOK_BYTES or len(signature) > 4096:
        raise billing.error(400, "INVALID_SIGNATURE", "Invalid webhook signature")
    try:
        parts = [part.split("=", 1) for part in signature.split(",")]
        timestamps = [value for key, value in parts if key == "t"]
        signatures = [value for key, value in parts if key == "v1"]
        if len(timestamps) != 1 or abs(time.time() - int(timestamps[0])) > 300:
            raise ValueError()
        expected = hmac.new(
            get_settings().stripe_webhook_secret.encode(),
            timestamps[0].encode() + b"." + raw,
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, value) for value in signatures):
            raise ValueError()
    except (ValueError, TypeError):
        raise billing.error(400, "INVALID_SIGNATURE", "Invalid webhook signature") from None
    event = _event(raw)
    if event.get("livemode") is not (get_settings().billing_environment == "live"):
        raise billing.error(400, "PAYMENT_ENVIRONMENT_MISMATCH", "Wrong payment environment")
    return event


def stripe_webhook(db, raw, signature):
    event = verify_stripe(raw, signature)
    if event.get("type") not in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        return {"received": True}
    try:
        session = event["data"]["object"]
        order = db.get(PaymentOrder, session["metadata"]["order_id"])
        if not order or order.provider != "stripe" or order.provider_order_id != session.get("id"):
            raise ValueError()
        if session.get("payment_status") != "paid":
            return {"received": True}
        with _client() as client:
            verified = _json(
                client.get(
                    "https://api.stripe.com/v1/checkout/sessions/" + order.provider_order_id,
                    headers={"Authorization": f"Bearer {get_settings().stripe_secret_key}"},
                )
            )
        if (
            verified.get("id") != order.provider_order_id
            or verified.get("metadata", {}).get("order_id") != order.id
            or verified.get("client_reference_id") != order.id
            or verified.get("mode") != "payment"
            or verified.get("payment_status") != "paid"
            or verified.get("currency") != "eur"
            or type(verified.get("amount_total")) is not int
            or verified["amount_total"] != order.amount_cents
            or verified.get("livemode") is not (get_settings().billing_environment == "live")
        ):
            raise ValueError()
    except httpx.HTTPError:
        raise billing.error(
            502,
            "PAYMENT_VERIFICATION_UNAVAILABLE",
            "Payment verification unavailable; retry delivery",
        ) from None
    except (KeyError, ValueError, TypeError, AttributeError):
        raise billing.error(400, "PAYMENT_ORDER_MISMATCH", "Payment does not match order") from None
    billing.credit_paid_order(db, order.id, "stripe", event["id"])
    return {"received": True}


def verify_paypal(raw, headers):
    require("paypal")
    event = _event(raw)
    fields = {
        "auth_algo": "paypal-auth-algo",
        "cert_url": "paypal-cert-url",
        "transmission_id": "paypal-transmission-id",
        "transmission_sig": "paypal-transmission-sig",
        "transmission_time": "paypal-transmission-time",
    }
    values = {key: headers.get(header, "") for key, header in fields.items()}
    if any(not value or len(value) > 4096 for value in values.values()):
        raise billing.error(400, "INVALID_SIGNATURE", "Missing PayPal signature headers")
    cert = urlparse(values["cert_url"])
    if (
        cert.scheme != "https"
        or cert.hostname not in {"api.paypal.com", "api.sandbox.paypal.com"}
        or cert.username
        or cert.password
        or cert.port not in (None, 443)
        or not cert.path.startswith("/v1/notifications/certs/")
    ):
        raise billing.error(400, "INVALID_SIGNATURE", "Invalid PayPal certificate URL")
    values["webhook_id"] = get_settings().paypal_webhook_id
    # PayPal requires the original webhook object bytes; do not reserialize it.
    body = json.dumps(values).encode()[:-1] + b',"webhook_event":' + raw + b"}"
    try:
        with _client() as client:
            token = _paypal_token(client)
            data = _json(
                client.post(
                    _paypal_base() + "/v1/notifications/verify-webhook-signature",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    content=body,
                )
            )
    except (httpx.HTTPError, ValueError, TypeError):
        raise billing.error(
            502,
            "PAYMENT_VERIFICATION_UNAVAILABLE",
            "PayPal verification unavailable; retry delivery",
        ) from None
    if data.get("verification_status") != "SUCCESS":
        raise billing.error(400, "INVALID_SIGNATURE", "PayPal webhook verification failed")
    return event


def paypal_webhook(db, raw, headers):
    event = verify_paypal(raw, headers)
    if event.get("event_type") != "PAYMENT.CAPTURE.COMPLETED":
        return {"received": True}
    try:
        capture = event["resource"]
        provider_id = capture["supplementary_data"]["related_ids"]["order_id"]
        order = (
            db.query(PaymentOrder)
            .filter_by(provider="paypal", provider_order_id=provider_id)
            .first()
        )
        amount = Decimal(capture["amount"]["value"]) * 100
        if (
            not order
            or capture.get("status") != "COMPLETED"
            or capture.get("final_capture") is not True
            or capture["amount"]["currency_code"] != "EUR"
            or amount != order.amount_cents
            or capture["payee"]["merchant_id"] != get_settings().paypal_merchant_id
        ):
            raise ValueError()
    except (KeyError, ValueError, TypeError, AttributeError, InvalidOperation):
        raise billing.error(
            400, "PAYMENT_ORDER_MISMATCH", "PayPal capture does not match order"
        ) from None
    billing.credit_paid_order(db, order.id, "paypal", event["id"])
    return {"received": True}
