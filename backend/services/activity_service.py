"""Privacy-conscious usage metadata: fixed event names, no IPs, queries or payloads."""

import logging
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from backend.database import SessionLocal
from backend.models import Activity, DailyMetric

EVENTS = {
    ("POST", "/api/account/register"): "account.register",
    ("POST", "/api/account/login"): "account.login",
    ("POST", "/api/account/recover"): "account.recover",
    ("POST", "/api/account/logout"): "account.logout",
    ("POST", "/api/session"): "session.start",
    ("POST", "/api/upload-cv"): "cv.upload",
    ("POST", "/api/job/import"): "job.import",
    ("POST", "/api/package"): "package.generate",
    ("POST", "/api/package/refine"): "package.refine",
    ("POST", "/api/generate"): "cv.generate",
    ("POST", "/api/refine"): "cv.refine",
    ("POST", "/api/projects"): "project.save",
    ("POST", "/api/export"): "document.export",
    ("POST", "/api/assistant"): "boosty.question",
    ("DELETE", "/api/account"): "account.delete",
}


def record(event=None, status=200, account_id=None, page=False, visit=False):
    try:
        with SessionLocal() as db:
            if event:
                db.add(Activity(event=event, outcome=status, account_id=account_id))
            if page or visit:
                day = datetime.now(UTC).date().isoformat()
                # Atomic increments and insert race recovery keep counts consistent.
                change = {
                    DailyMetric.page_views: DailyMetric.page_views + int(page),
                    DailyMetric.visits: DailyMetric.visits + int(visit),
                }
                if not db.execute(
                    update(DailyMetric).where(DailyMetric.day == day).values(change)
                ).rowcount:
                    try:
                        with db.begin_nested():
                            db.add(DailyMetric(day=day, page_views=int(page), visits=int(visit)))
                            db.flush()
                    except IntegrityError:
                        db.execute(update(DailyMetric).where(DailyMetric.day == day).values(change))
            db.commit()
    except Exception:
        # Telemetry must not expose or break user content processing.
        logging.getLogger(__name__).warning("Usage metric could not be saved")
