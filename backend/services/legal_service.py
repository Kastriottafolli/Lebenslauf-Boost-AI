"""Standalone legal pages and immutable text copies of contractual information."""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTES = {"legal": "impressum", "privacy": "datenschutz", "terms": "agb", "withdrawal": "widerruf"}
LABELS = {
    "de": {
        "legal": "Impressum",
        "privacy": "Datenschutz",
        "terms": "AGB",
        "withdrawal": "Widerruf",
        "back": "Zur Startseite",
        "copy": "Textkopie herunterladen",
        "account": "Vertrag im Konto widerrufen",
    },
    "en": {
        "legal": "Legal notice",
        "privacy": "Privacy",
        "terms": "Terms",
        "withdrawal": "Withdrawal",
        "back": "Back to home",
        "copy": "Download text copy",
        "account": "Withdraw from contract in account",
    },
    "sq": {
        "legal": "Të dhënat ligjore",
        "privacy": "Privatësia",
        "terms": "Kushtet",
        "withdrawal": "Tërheqja",
        "back": "Kthehu në fillim",
        "copy": "Shkarko kopjen e tekstit",
        "account": "Tërhiqu nga kontrata në llogari",
    },
}


def content_data(language="de", operator=None, retention_days=30):
    language = language if language in LABELS else "de"
    brand = json.loads((ROOT / "static/branding.json").read_text())
    config = json.loads((ROOT / "static/legal-config.json").read_text())
    data = {
        **brand["operator"],
        **(operator or {}),
        **config,
        "retention_days": str(retention_days),
    }
    for name in ("hosting_name", "hosting_country", "hosting_retention", "backup_retention"):
        value = data.get(name)
        if isinstance(value, dict):
            value = value.get(language) or value.get("de")
        data[name] = (
            value
            or {"de": "Noch nicht festgelegt", "en": "Not yet set", "sq": "Ende pa vendosur"}[
                language
            ]
        )
    return language, brand, config, data


def rows_for(kind, language, config):
    rows = json.loads((ROOT / "static/legal-texts.json").read_text())[language][kind]
    if kind == "legal":
        fields = [
            ("business_name", "Firma / Company"),
            ("legal_form", "Rechtsform / Legal form"),
            ("phone", "Telefon / Phone"),
            ("register", "Register"),
            ("vat_id", "USt-ID / VAT ID"),
            ("economic_id", "Wirtschafts-ID"),
            ("representative", "Vertretung / Representative"),
            ("supervisory_authority", "Aufsichtsbehörde / Supervisory authority"),
            ("professional_rules", "Berufsrechtliche Angaben / Professional rules"),
            ("editorial_responsible", "Redaktionell verantwortlich / Editorial contact"),
            ("dispute_resolution", "Verbraucherstreitbeilegung / Dispute resolution"),
        ]
        extra = [label + ": " + config[field] for field, label in fields if config.get(field)]
        if extra:
            rows = [*rows, ("Weitere Anbieterangaben / Additional information", "\n".join(extra))]
    return rows


def render_text(kind="terms", language="de", operator=None, retention_days=30):
    """Return the exact version as plain text for email/contract snapshots."""
    if kind not in ROUTES:
        raise ValueError("Unknown legal document")
    language, brand, config, data = content_data(language, operator, retention_days)
    rows = rows_for(kind, language, config)
    parts = [LABELS[language][kind] + " | " + brand["name"], "Version: " + config["updated"]]
    parts.extend(heading + "\n" + content.format_map(data) for heading, content in rows)
    return "\n\n".join(parts) + "\n"


def render(
    kind="legal",
    language="de",
    operator=None,
    site_url="",
    prefix="/",
    retention_days=30,
    static_routes=False,
):
    if kind not in ROUTES:
        raise ValueError("Unknown legal document")
    language, brand, config, data = content_data(language, operator, retention_days)
    labels = LABELS[language]
    title = labels[kind]
    brand_name = html.escape(brand["name"])
    rows = rows_for(kind, language, config)
    sections = []
    for index, (heading, content) in enumerate(rows):
        value = html.escape(content.format_map(data)).replace("\n", "<br>")
        value = value.replace(
            "https://www.datenschutz-mv.de/",
            '<a href="https://www.datenschutz-mv.de/" rel="noopener noreferrer">www.datenschutz-mv.de</a>',
        )
        sections.append(
            f'<section id="section-{index}"><h2>{html.escape(heading)}</h2><p>{value}</p></section>'
        )
    route = ROUTES[kind]
    lang_links = " ".join(
        f'<a href="{prefix + route + "/" + (lang + "/" if lang != "de" else "") if static_routes else "?lang=" + lang}">{name}</a>'
        for lang, name in [("de", "Deutsch"), ("en", "English"), ("sq", "Shqip")]
    )
    toc = "".join(
        f'<li><a href="#section-{i}">{html.escape(row[0])}</a></li>' for i, row in enumerate(rows)
    )
    canonical = (
        f'<link rel="canonical" href="{html.escape(site_url.rstrip("/"), quote=True)}/{route}/">'
        if site_url
        else ""
    )
    footer = "".join(
        f'<a href="{prefix}{ROUTES[name]}/{(language + "/") if static_routes and language != "de" else ""}{"?lang=" + language if not static_routes else ""}">{labels[name]}</a>'
        for name in ROUTES
    )
    copy_href = "document.txt" if static_routes else f"/{route}.txt?lang={language}"
    extra = (
        f'<p><a href="{html.escape(copy_href, quote=True)}" download>{labels["copy"]}</a></p>'
        if kind in ("terms", "withdrawal")
        else ""
    )
    if kind == "withdrawal":
        extra += f'<p><a class="button primary" href="{prefix}?lang={language}&amp;account=login#account-credits">{labels["account"]}</a></p>'
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | {brand_name}</title>{canonical}<link rel="icon" href="{prefix}static/boosty-3d.png" type="image/png"><link rel="stylesheet" href="{prefix}assets/css/professional.css"></head><body><header class="topbar"><a class="brand" href="{prefix}"><img src="{prefix}static/boosty-3d.png" width="44" height="48" alt="Boosty">{brand_name}</a><nav aria-label="Language">{lang_links}</nav></header><main class="guide legal-page"><a href="{prefix}">{labels["back"]} →</a><h1>{title}</h1>{extra}<nav aria-label="Contents"><ol>{toc}</ol></nav>{"".join(sections)}<p>Stand / Updated: {config["updated"]}</p></main><footer>{footer}<a href="mailto:{html.escape(data["operator_email"], quote=True)}">{html.escape(data["operator_email"])}</a></footer></body></html>'''
