"""Orchestrierung: Einzel-Generierung, Vergleichsanalyse, Verfeinern, Demo-Fallback."""

from typing import Dict, List, Optional

from .. import rag
from ..config import get_settings
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider

settings = get_settings()


def get_provider(name: str, keys: Optional[dict] = None):
    keys = keys or {}
    if name == "claude":
        return AnthropicProvider(api_key=keys.get("anthropic"))
    if name == "openai":
        return OpenAIProvider(api_key=keys.get("openai"))
    return None


def provider_status() -> Dict[str, bool]:
    return {
        "claude": AnthropicProvider().available(),
        "openai": OpenAIProvider().available(),
    }


def run_generation(
    provider_name: str,
    system: str,
    messages: List[Dict[str, str]],
    *,
    language: str,
    demo_payload: dict,
    keys: Optional[dict] = None,
) -> dict:
    """Ruft den Anbieter auf — oder erzeugt eine klar markierte Demo-Ausgabe."""
    provider = get_provider(provider_name, keys)
    if provider and provider.available():
        try:
            result = provider.generate(system, messages)
            if result.content.strip():
                return {
                    "content": result.content,
                    "provider": result.provider,
                    "model": result.model,
                    "is_demo": False,
                }
        except Exception as exc:  # robuste Fehlerkorrektur -> Demo statt Crash
            return {
                "content": _demo_cv(demo_payload, language, error=str(exc)),
                "provider": provider_name,
                "model": "demo",
                "is_demo": True,
            }

    return {
        "content": _demo_cv(demo_payload, language),
        "provider": provider_name,
        "model": "demo",
        "is_demo": True,
    }


def recommend(results: List[dict], language: str) -> dict:
    """Use-Case-spezifische Vergleichsanalyse zweier Anbieter."""
    ranked = sorted(results, key=lambda r: r["analysis"]["ats_score"], reverse=True)
    winner = ranked[0]
    loser = ranked[-1]
    wp, lp = winner["provider"], loser["provider"]
    ws = winner["analysis"]["ats_score"]
    ls = loser["analysis"]["ats_score"]

    if language == "en":
        text = (
            f"{wp.upper()} scores higher on ATS keyword coverage "
            f"({ws}% vs {ls}%) for this posting. "
            f"Both drafts are saved — pick the one you prefer."
        )
        if ws == ls:
            text = (
                f"Both providers reach {ws}% ATS coverage. "
                f"Compare tone and wording and choose your favorite."
            )
    else:
        text = (
            f"{wp.upper()} erreicht eine höhere ATS-Keyword-Abdeckung "
            f"({ws}% vs. {ls}%) für diese Stelle. "
            f"Beide Entwürfe sind gespeichert — wähle deinen Favoriten."
        )
        if ws == ls:
            text = (
                f"Beide Anbieter erreichen {ws}% ATS-Abdeckung. "
                f"Vergleiche Ton und Formulierung und wähle deinen Favoriten."
            )

    return {"winner_provider": wp, "recommendation": text}


# ──────────────────────────────────────────────────────────────────────────
# Demo-Fallback (ohne API-Key) — regelbasiert, klar gekennzeichnet
# ──────────────────────────────────────────────────────────────────────────
def _demo_cv(payload: dict, language: str, error: Optional[str] = None) -> str:
    cv_full: str = payload.get("cv_full", "") or ""
    job_desc: str = payload.get("job_description", "")
    wishes: str = payload.get("wishes", "")
    keywords = rag.extract_keywords(job_desc, limit=12)

    lines = [ln.strip() for ln in cv_full.splitlines() if ln.strip()]
    name = lines[0] if lines else ("Your Name" if language == "en" else "Vor- und Nachname")
    title = lines[1] if len(lines) > 1 else (
        "Target Role" if language == "en" else "Zielposition"
    )
    contact = next(
        (ln for ln in lines[:6] if "@" in ln or any(c.isdigit() for c in ln)),
        "email@example.com | +49 …",
    )

    body = "\n".join(f"- {ln}" for ln in lines[2:10]) if len(lines) > 2 else (
        "- (Lebenslauf-Inhalte erscheinen hier)"
    )
    skills = ", ".join(keywords) if keywords else "—"

    if language == "en":
        note = "> ⚠️ DEMO MODE: no API key set — this is a rule-based preview, not AI output."
        if error:
            note = f"> ⚠️ DEMO MODE (provider error): {error[:160]}"
        wishblock = f"\n## Notes\n- Requested focus: {wishes}\n" if wishes else ""
        return (
            f"{note}\n\n"
            f"# {name}\n{title}\n{contact}\n\n"
            f"## Summary\nExperienced professional aligned to the target role, "
            f"highlighting strengths relevant to the posting.\n\n"
            f"## Experience\n{body}\n\n"
            f"## Skills\n- {skills}\n{wishblock}"
        )

    note = "> ⚠️ DEMO-MODUS: Kein API-Key gesetzt — regelbasierte Vorschau, keine KI-Ausgabe."
    if error:
        note = f"> ⚠️ DEMO-MODUS (Anbieter-Fehler): {error[:160]}"
    wishblock = f"\n## Hinweise\n- Gewünschter Fokus: {wishes}\n" if wishes else ""
    return (
        f"{note}\n\n"
        f"# {name}\n{title}\n{contact}\n\n"
        f"## Profil\nErfahrene Fachkraft, ausgerichtet auf die Zielposition, "
        f"mit Fokus auf die für die Stelle relevanten Stärken.\n\n"
        f"## Berufserfahrung\n{body}\n\n"
        f"## Fähigkeiten\n- {skills}\n{wishblock}"
    )
