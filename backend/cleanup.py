"""Delete expired anonymous sessions. Run daily; account projects stay until deleted."""

from datetime import UTC, datetime, timedelta

from backend.config import get_settings
from backend.database import SessionLocal, init_db
from backend.models import (
    Activity,
    AdminAudit,
    AdminLogin,
    Application,
    AssistantQuota,
    AuthAttempt,
    DailyMetric,
    Login,
    Session,
)


def cleanup():
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        days=max(1, get_settings().retention_days)
    )
    with SessionLocal() as db:
        from backend.services import billing_service

        now = datetime.now(UTC).replace(tzinfo=None)
        from backend.account_models import AccountActionToken, AccountSecurity, EmailOutbox
        from backend.models import Account, AdminAccess

        db.query(AccountActionToken).filter(AccountActionToken.expires_at <= now).delete()
        db.query(EmailOutbox).filter(
            EmailOutbox.expires_at <= now, EmailOutbox.payload_cipher.is_not(None)
        ).update({"status": "failed", "payload_cipher": None, "lease_until": None})
        db.query(EmailOutbox).filter(EmailOutbox.created_at < now - timedelta(days=7)).delete()
        # Never-confirmed registrations contain no signed-in documents. Remove them
        # after 14 days without affecting legacy users, social users or admin access.
        abandoned_ids = [account_id for (account_id,) in db.query(Account.id).join(
            AccountSecurity, Account.id == AccountSecurity.account_id
        ).filter(
            AccountSecurity.verified_at.is_(None),
            AccountSecurity.verification_source == "email_pending",
            Account.created_at < now - timedelta(days=14),
            ~db.query(AdminAccess.account_id).filter(AdminAccess.account_id == Account.id).exists(),
        ).all()]
        if abandoned_ids:
            db.query(Account).filter(Account.id.in_(abandoned_ids)).delete(synchronize_session=False)
        billing_service.purge_cached_responses(db, expired_at=now)
        db.query(AdminLogin).filter(AdminLogin.expires_at <= now).delete()
        db.query(AuthAttempt).filter(AuthAttempt.created_at < now - timedelta(minutes=15)).delete()
        db.query(AssistantQuota).filter(
            AssistantQuota.day < (now - timedelta(days=30)).date().isoformat()
        ).delete()
        db.query(Activity).filter(Activity.created_at < now - timedelta(days=30)).delete()
        db.query(AdminAudit).filter(AdminAudit.created_at < now - timedelta(days=90)).delete()
        db.query(DailyMetric).filter(
            DailyMetric.day < (now - timedelta(days=90)).date().isoformat()
        ).delete()
        from backend.models import AIBudget, AICall, OAuthState

        db.query(OAuthState).filter(
            OAuthState.expires_at <= datetime.now(UTC).replace(tzinfo=None)
        ).delete()
        db.query(AICall).filter(AICall.day < (now - timedelta(days=30)).date().isoformat()).delete()
        db.query(AIBudget).filter(
            AIBudget.day < (now - timedelta(days=30)).date().isoformat()
        ).delete()
        db.query(Login).filter(Login.expires_at <= datetime.now(UTC).replace(tzinfo=None)).delete()
        sessions = (
            db.query(Session).filter(Session.owner_id.is_(None), Session.created_at < cutoff).all()
        )
        for sess in sessions:
            project_ids = [
                project_id
                for (project_id,) in db.query(Application.id).filter_by(session_id=sess.id).all()
            ]
            billing_service.purge_cached_responses(
                db, session_ids=[sess.id], project_ids=project_ids
            )
            db.query(Application).filter_by(session_id=sess.id).delete()
            db.delete(sess)
        db.commit()
        return len(sessions)


if __name__ == "__main__":
    init_db()
    print(f"Deleted {cleanup()} expired anonymous sessions.")
