"""Consent-based traffic data, deliberately separate from accounts and DailyMetric.

Only a random, short-lived capability hash can address a visit. No account key,
raw IP, user agent, referrer, query string or browser fingerprint belongs here.
"""

import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String

from backend.database import Base


class TrafficVisit(Base):
    __tablename__ = "traffic_visits"
    __table_args__ = (
        CheckConstraint("device IN ('desktop','mobile','tablet','bot')", name="ck_traffic_device"),
        CheckConstraint("active_seconds >= 0 AND active_seconds <= 86400", name="ck_traffic_active"),
        CheckConstraint("elapsed_seconds >= active_seconds AND elapsed_seconds <= 86400", name="ck_traffic_elapsed"),
        CheckConstraint("client_active_seconds >= 0 AND client_active_seconds <= 86400", name="ck_traffic_client_active"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash = Column(String(64), nullable=True, unique=True)
    token_expires_at = Column(DateTime, nullable=True, index=True)
    started_at = Column(DateTime, nullable=False, index=True)
    last_seen_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    page = Column(String(24), nullable=False)
    device = Column(String(7), nullable=False)
    country_code = Column(String(2), nullable=False, default="")
    ip_masked = Column(String(48), nullable=True)
    active_seconds = Column(Integer, nullable=False, default=0)
    elapsed_seconds = Column(Integer, nullable=False, default=0)
    client_active_seconds = Column(Integer, nullable=False, default=0)
    revision = Column(Integer, nullable=False, default=0)


class TrafficDaily(Base):
    """Anonymous totals retained after the disposable visit detail is removed."""

    __tablename__ = "traffic_daily"
    __table_args__ = (
        CheckConstraint("visits >= 0 AND active_seconds >= 0 AND elapsed_seconds >= 0", name="ck_traffic_daily_nonnegative"),
    )

    day = Column(String(10), primary_key=True)
    page = Column(String(24), primary_key=True)
    device = Column(String(7), primary_key=True)
    country_code = Column(String(2), primary_key=True, default="")
    visits = Column(Integer, nullable=False, default=0)
    active_seconds = Column(Integer, nullable=False, default=0)
    elapsed_seconds = Column(Integer, nullable=False, default=0)


def init_traffic_schema(engine):
    """Add these tables to an existing installation without rebuilding its tables."""
    Base.metadata.create_all(engine, tables=[TrafficVisit.__table__, TrafficDaily.__table__])
