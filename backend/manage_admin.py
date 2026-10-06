"""Server-owner-only admin provisioning. No web endpoint grants administrator rights."""

import argparse
from pathlib import Path

from backend.database import SessionLocal, init_db
from backend.services.admin_service import normalized_email, provision, rename_email


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--directory", type=Path, default=Path("data/private"))
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--reset-existing",
        action="store_true",
        help="Nur ein bereits provisioniertes Adminkonto zurücksetzen; alle Admin-Sitzungen werden ungültig.",
    )
    operation.add_argument(
        "--rename-from",
        help="E-Mail eines aktiven Adminkontos korrigieren; Passwort, Authenticator und Daten bleiben erhalten.",
    )
    args = parser.parse_args()
    try:
        email = normalized_email(args.email)
        source_email = normalized_email(args.rename_from) if args.rename_from else None
    except ValueError as error:
        parser.error(str(error))
    init_db()
    with SessionLocal() as db:
        try:
            if source_email:
                rename_email(db, source_email, email)
            else:
                destination = provision(db, email, args.directory, args.reset_existing)
        except ValueError as error:
            parser.error(str(error))
    if source_email:
        print(f"Admin-E-Mail korrigiert: {email}. Bestehendes Passwort und Authenticator bleiben gültig.")
        print("Alle bisherigen Anmeldungen wurden beendet. Mit neuer Adresse und neuem Zeitcode anmelden.")
        return
    print(f"Admin zur Einrichtung vorbereitet. Private Anleitung: {destination.resolve()}")
    print(
        "Kein Standardpasswort. Einrichtung unter /admin; Code wird nicht im Terminal ausgegeben."
    )


if __name__ == "__main__":
    main()
