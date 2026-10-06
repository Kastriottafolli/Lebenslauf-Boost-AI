"""Cron-compatible transactional email delivery. Outputs counts only."""

from backend.database import init_db
from backend.services.account_mail import drain

if __name__ == "__main__":
    init_db()
    results = drain(limit=100)
    print(f"Transactional mail: sent={results['sent']}, retry_or_failed={results['failed']}")
