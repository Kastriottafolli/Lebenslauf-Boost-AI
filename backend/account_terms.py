"""Versioned, auditable acknowledgement of the actual service terms."""

from fastapi import HTTPException

TERMS_VERSION = "2026-10-06"
PRIVACY_VERSION = "2026-10-06"


def require_current_terms(db, account):
    from backend.account_models import AccountSecurity

    security = db.get(AccountSecurity, account.id)
    if (
        not security
        or security.terms_version != TERMS_VERSION
        or security.privacy_version != PRIVACY_VERSION
    ):
        raise HTTPException(
            403,
            {
                "code": "TERMS_ACCEPTANCE_REQUIRED",
                "message": "Bitte die aktuellen AGB annehmen und die Datenschutzhinweise lesen.",
            },
        )
    return security


def queue_terms_receipt(db, account, language="de"):
    from backend.config import get_settings
    from backend.services import account_mail, legal_service

    security = require_current_terms(db, account)
    settings = get_settings()
    operator = {
        "operator_name": settings.operator_name,
        "operator_address": settings.operator_address,
        "operator_email": settings.operator_email,
    }
    language = language if language in {"de", "en", "sq"} else "de"
    subject, intro = {
        "de": ("Dein TafolliBoost-Konto und deine Vertragsunterlagen", "Dein TafolliBoost-Konto ist aktiv. Diese E-Mail enthält eine dauerhafte Kopie der angenommenen AGB und der Widerrufsinformationen. Die Kontoeröffnung ist kostenlos und keine kostenpflichtige Bestellung."),
        "en": ("Your TafolliBoost account and contract documents", "Your TafolliBoost account is active. This email includes a durable copy of the accepted terms and withdrawal information. Opening an account is free and does not place a paid order."),
        "sq": ("Llogaria jote TafolliBoost dhe dokumentet e kontratës", "Llogaria jote TafolliBoost është aktive. Ky email përmban një kopje të qëndrueshme të kushteve të pranuara dhe të informacionit për tërheqjen. Hapja e llogarisë është falas dhe nuk përbën porosi me pagesë."),
    }[language]
    text = (
        intro + "\n\nVersion: " + TERMS_VERSION + "\nUTC: "
        + security.terms_accepted_at.isoformat() + "\n\n"
        + legal_service.render_text("terms", language, operator, settings.retention_days)
        + "\n\n" + legal_service.render_text("withdrawal", language, operator, settings.retention_days)
    )
    return account_mail.queue_receipt(db, account, subject, text, language)
