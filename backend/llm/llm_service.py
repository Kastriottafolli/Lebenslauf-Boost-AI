"""AI orchestration with explicit demos and errors, no silent fallbacks."""

from backend.config import get_settings
from backend.llm.http_provider import PROVIDERS, HTTPProvider

settings = get_settings()


def get_provider(name, keys=None, model=None, endpoint=None):
    keys = keys or {}
    config = PROVIDERS.get(name)
    if not config:
        return None
    key = keys.get(config["key"]) or ""
    if not key and settings.allow_server_keys:
        key = getattr(settings, f"{config['key']}_api_key", "")
    return HTTPProvider(
        name,
        key,
        model or getattr(settings, f"{config['key']}_model", None),
        endpoint or settings.azure_endpoint,
    )


def provider_status():
    return {name: get_provider(name).available() for name in PROVIDERS}


def run_generation(
    provider_name,
    system,
    messages,
    *,
    language,
    demo_payload,
    keys=None,
    model=None,
    endpoint=None,
):
    provider = get_provider(provider_name, keys, model, endpoint)
    if provider and provider.available():
        result = provider.generate(system, messages)
        return {
            "content": result.content,
            "provider": result.provider,
            "model": result.model,
            "is_demo": False,
        }
    return {
        "content": _demo_cv(demo_payload, language),
        "provider": provider_name,
        "model": "demo",
        "is_demo": True,
    }


def recommend(results, language):
    return {
        "winner_provider": None,
        "recommendation": "Compare the drafts and verify every fact. Keyword coverage is not a hiring probability."
        if language == "en"
        else "Vergleiche die Entwürfe und prüfe alle Angaben. Keyword-Abdeckung ist keine Einstellungswahrscheinlichkeit.",
    }


def _demo_cv(payload, language, error=None):
    source = payload.get("cv_full", "").strip()
    if not source.startswith("# "):
        source = "# " + source
    note = (
        "> DEMO: Rule-based source formatting. No AI request."
        if language == "en"
        else "> DEMO: Regelbasierte Aufbereitung deiner Angaben. Keine KI-Anfrage."
    )
    return source + "\n\n" + note
