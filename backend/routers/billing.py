"""Web-only payment preparation: private balance and signed provider callbacks."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AdminAccess
from backend.services import billing_service as billing
from backend.services import payment_service as payments
from backend.services.account_service import current_account

router = APIRouter(prefix="/api/billing", tags=["Billing"])


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offer_id: Literal["single", "bundle10"]
    provider: Literal["stripe", "paypal"]
    request_id: UUID


def _account(db, request):
    account = current_account(db, request, True)
    if db.get(AdminAccess, account.id):
        raise billing.error(403, "USER_ACCOUNT_REQUIRED", "Please use a regular user account")
    return account


@router.get("/pricing")
def pricing():
    return payments.pricing()


@router.get("/balance")
def balance(request: Request, db: Session = Depends(get_db)):
    return billing.balance(db, _account(db, request).id)


@router.post("/checkout")
def checkout(req: CheckoutRequest, request: Request, db: Session = Depends(get_db)):
    return payments.checkout(
        db, _account(db, request).id, req.request_id, req.provider, req.offer_id
    )


@router.get("/orders/{order_id}")
def order_status(order_id: UUID, request: Request, db: Session = Depends(get_db)):
    from backend.models import PaymentOrder

    account = _account(db, request)
    order = db.get(PaymentOrder, str(order_id))
    if not order or order.account_id != account.id:
        raise billing.error(404, "ORDER_NOT_FOUND", "Payment order not found")
    return {"order_id": order.id, "status": order.status, "credits": order.credits}


@router.post("/paypal/capture/{order_id}")
def capture(order_id: UUID, request: Request, db: Session = Depends(get_db)):
    return payments.capture_paypal(db, _account(db, request).id, str(order_id))


async def _raw_body(request):
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > payments.MAX_WEBHOOK_BYTES:
            raise billing.error(413, "WEBHOOK_TOO_LARGE", "Webhook body too large")
    return bytes(raw)


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    from starlette.concurrency import run_in_threadpool

    payments.require("stripe")
    raw = await _raw_body(request)
    return await run_in_threadpool(
        payments.stripe_webhook, db, raw, request.headers.get("stripe-signature", "")
    )


@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request, db: Session = Depends(get_db)):
    from starlette.concurrency import run_in_threadpool

    payments.require("paypal")
    raw = await _raw_body(request)
    return await run_in_threadpool(payments.paypal_webhook, db, raw, request.headers)
