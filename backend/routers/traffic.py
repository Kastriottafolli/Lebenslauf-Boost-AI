"""Optional telemetry: no cookies, account identity or user-provided geography."""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from backend.database import get_db
from backend.services import traffic_service as traffic

router = APIRouter(prefix="/api/traffic", tags=["Consent-based traffic"])
TOKEN_PATTERN = r"^[A-Za-z0-9_-]{43}$"


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page: str = Field(max_length=24)
    analytics_consent: StrictBool

    @field_validator("page")
    @classmethod
    def public_page(cls, value):
        if value not in traffic.PAGES:
            raise ValueError("Unknown public page label")
        return value

    @field_validator("analytics_consent")
    @classmethod
    def consent_required(cls, value):
        if value is not True:
            raise ValueError("Analytics consent required")
        return value


class PulseRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    visit_token: str = Field(pattern=TOKEN_PATTERN, min_length=43, max_length=43)
    active_seconds: int = Field(ge=0, le=traffic.MAX_VISIT_SECONDS, strict=True)


class EndRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    visit_token: str = Field(pattern=TOKEN_PATTERN, min_length=43, max_length=43)
    active_seconds: int | None = Field(default=None, ge=0, le=traffic.MAX_VISIT_SECONDS, strict=True)
    withdraw: StrictBool = False


def _client_ip(request):
    return request.client.host if request.client else None


def _optional_metric(db, function, **kwargs):
    from fastapi import HTTPException

    try:
        return function(db, **kwargs)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logging.getLogger(__name__).warning("Traffic metric could not be saved")
        return {"ok": False, "disabled": True}


@router.post("/start")
def start(payload: StartRequest, request: Request, db=Depends(get_db)):
    traffic.limit_request(_client_ip(request), "start")
    return _optional_metric(db, traffic.start, page=payload.page, analytics_consent=payload.analytics_consent,
        client_ip=_client_ip(request), user_agent=request.headers.get("user-agent", ""))


@router.post("/heartbeat")
def heartbeat(payload: PulseRequest, request: Request, db=Depends(get_db)):
    traffic.limit_request(_client_ip(request), "pulse", payload.visit_token)
    return _optional_metric(db, traffic.pulse, token=payload.visit_token, active_seconds=payload.active_seconds)


@router.post("/end")
def end(payload: EndRequest, request: Request, db=Depends(get_db)):
    # A consent withdrawal remains available even after a heartbeat budget is spent.
    if not payload.withdraw:
        traffic.limit_request(_client_ip(request), "pulse", payload.visit_token)
    else:
        traffic.limit_request(_client_ip(request), "withdraw")
    return _optional_metric(db, traffic.pulse, token=payload.visit_token, active_seconds=payload.active_seconds,
        end=True, withdraw=payload.withdraw)
