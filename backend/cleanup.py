"""Delete expired anonymous sessions. Run daily; account projects stay until deleted."""

from datetime import UTC, datetime, timedelta

from backend.config import get_settings
from backend.database import SessionLocal, init_db
from backend.models import Application, Session


def cleanup():
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        days=max(1, get_settings().retention_days)
    )
    with SessionLocal() as db:
        sessions = (
            db.query(Session).filter(Session.owner_id.is_(None), Session.created_at < cutoff).all()
        )
        for sess in sessions:
            db.query(Application).filter_by(session_id=sess.id).delete()
            db.delete(sess)
        db.commit()
        return len(sessions)


if __name__ == "__main__":
    init_db()
    print(f"Deleted {cleanup()} expired anonymous sessions.")
