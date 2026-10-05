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
