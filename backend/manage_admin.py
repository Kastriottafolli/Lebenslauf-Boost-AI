"""Server-owner-only admin provisioning. No web endpoint grants administrator rights."""

import argparse
import re
from pathlib import Path

from backend.database import SessionLocal, init_db
from backend.services.admin_service import provision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--directory", type=Path, default=Path("data/private"))
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Nur ein bereits provisioniertes Adminkonto zurücksetzen; alle Admin-Sitzungen werden ungültig.",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", args.email.strip()):
        parser.error("Ungültige E-Mail")
    init_db()
    with SessionLocal() as db:
        try:
            destination = provision(db, args.email, args.directory, args.reset_existing)
        except ValueError as error:
            parser.error(str(error))
    print(f"Admin zur Einrichtung vorbereitet. Private Anleitung: {destination.resolve()}")
    print(
        "Kein Standardpasswort. Einrichtung unter /admin; Code wird nicht im Terminal ausgegeben."
    )


if __name__ == "__main__":
    main()
