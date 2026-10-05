"""Readable standalone legal notices without inventing missing operator facts."""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def render(
    kind="legal",
    language="de",
    operator=None,
    site_url="",
    prefix="/",
    retention_days=30,
    static_routes=False,
):
    language = language if language in ("de", "en", "sq") else "de"
    brand = json.loads((ROOT / "static/branding.json").read_text())
    brand_name = html.escape(brand["name"])
    config = json.loads((ROOT / "static/legal-config.json").read_text())
    data = {
        **brand["operator"],
        **(operator or {}),
        **config,
        "retention_days": str(retention_days),
    }
    pending = {
        "de": "Noch nicht festgelegt – vor öffentlichem Betrieb ergänzen",
        "en": "Not yet set — complete before public launch",
        "sq": "Ende pa vendosur — plotëso përpara publikimit",
    }[language]
    for name in ("hosting_name", "hosting_country", "hosting_retention", "backup_retention"):
        value = data.get(name)
        if isinstance(value, dict):
            value = value.get(language) or value.get("de")
        data[name] = value or pending
    labels = {
        "de": (
            "Impressum",
            "Datenschutz",
            "Zur Bewerbung",
        ),
        "en": (
            "Legal notice",
            "Privacy",
            "Back to application",
        ),
        "sq": (
            "Të dhënat ligjore",
            "Privatësia",
            "Kthehu te aplikimi",
        ),
    }[language]
    title = labels[0 if kind == "legal" else 1]
    rows = json.loads((ROOT / "static/legal-texts.json").read_text())[language][kind]
    sections = []
    if kind == "legal":
        extra = []
        for field, label in [
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
        ]:
            if config[field]:
                extra.append(f"{label}: {config[field]}")
        if extra:
            rows = [*rows, ("Weitere Anbieterangaben / Additional information", "\n".join(extra))]
    for index, (heading, content) in enumerate(rows):
        value = html.escape(content.format_map(data)).replace("\n", "<br>")
        # Only fixed, reviewed references are linked; no user HTML is accepted.
        value = value.replace(
            "https://www.datenschutz-mv.de/",
            '<a href="https://www.datenschutz-mv.de/" rel="noopener noreferrer">www.datenschutz-mv.de</a>',
        )
        sections.append(
            f'<section id="section-{index}"><h2>{html.escape(heading)}</h2><p>{value}</p></section>'
        )
    route = "impressum" if kind == "legal" else "datenschutz"
    links = " ".join(
        f'<a href="{prefix + route + "/" + (lang + "/" if lang != "de" else "") if static_routes else "?lang=" + lang}">{name}</a>'
        for lang, name in [("de", "Deutsch"), ("en", "English"), ("sq", "Shqip")]
    )
    if kind == "privacy" and language != "de":
        summary = {
            "en": "English summary. The detailed German notice is available via Deutsch.",
            "sq": "Përmbledhje shqip. Teksti i detajuar gjerman gjendet te Deutsch.",
        }[language]
        sections.insert(0, f"<p>{summary}</p>")
    toc = "".join(
        f'<li><a href="#section-{i}">{html.escape(row[0])}</a></li>' for i, row in enumerate(rows)
    )
    canonical = (
        f'<link rel="canonical" href="{html.escape(site_url.rstrip("/"), quote=True)}/{route}/">'
        if site_url
        else ""
    )
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | {brand_name}</title>{canonical}<link rel="icon" href="{prefix}static/boosty-3d.png" type="image/png"><link rel="stylesheet" href="{prefix}assets/css/professional.css"></head><body><header class="topbar"><a class="brand" href="{prefix}"><img src="{prefix}static/boosty-3d.png" width="44" height="48" alt="Boosty">{brand_name}</a><nav aria-label="Language">{links}</nav></header><main class="guide legal-page"><a href="{prefix}">{labels[2]} →</a><h1>{title}</h1><nav aria-label="Contents"><ol>{toc}</ol></nav>{"".join(sections)}<p>Stand / Updated: {config["updated"]}</p></main><footer><a href="{prefix}impressum/">{labels[0]}</a><a href="{prefix}datenschutz/">{labels[1]}</a><a href="mailto:{html.escape(data["operator_email"], quote=True)}">{html.escape(data["operator_email"])}</a></footer></body></html>'''
