"""Additive account lifecycle tables; old accounts and admin tables stay intact."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text

from backend.database import Base
from backend.models import _uuid


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


class AccountSecurity(Base):
    __tablename__ = "account_security"
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    verified_at = Column(DateTime, nullable=True)
    verification_source = Column(String(24), nullable=False, default="email_pending")
    credential_version = Column(Integer, nullable=False, default=1)
    terms_version = Column(String(20), nullable=True)
    privacy_version = Column(String(20), nullable=True)
    terms_accepted_at = Column(DateTime, nullable=True)
    privacy_acknowledged_at = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)


class AccountProfile(Base):
    __tablename__ = "account_profiles"
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    display_name = Column(String(200), nullable=False, default="")
    first_name = Column(String(100), nullable=False, default="")
    last_name = Column(String(100), nullable=False, default="")
    phone = Column(String(100), nullable=False, default="")
    location = Column(String(300), nullable=False, default="")
    headline = Column(String(300), nullable=False, default="")
    language = Column(String(2), nullable=False, default="de")
    email_notifications = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=_now)


class AccountActionToken(Base):
    __tablename__ = "account_action_tokens"
    __table_args__ = (
        CheckConstraint("purpose IN ('verify','reset','change_email')", name="ck_account_token_purpose"),
    )
    token_hash = Column(String(64), primary_key=True)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(16), nullable=False)
    target_email = Column(String(254), nullable=False)
    credential_version = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)


class EmailOutbox(Base):
    """Links are encrypted at rest and removed after delivery/expiry; no SMTP logs."""

    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint("status IN ('pending','sending','sent','failed')", name="ck_mail_outbox_status"),
    )
    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient = Column(String(254), nullable=False)
    purpose = Column(String(24), nullable=False)
    payload_cipher = Column(Text, nullable=True)
    status = Column(String(12), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=False, default=_now, index=True)
    lease_until = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)
    sent_at = Column(DateTime, nullable=True)
