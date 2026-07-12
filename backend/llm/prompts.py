"""Prompt-Verwaltung.

Die eigentlichen Prompt-Texte liegen als Vorlagen im Ordner  prompts/
(Projekt-Root) — siehe prompts/README.md. Dieses Modul lädt sie (mit Cache)
und füllt die Platzhalter zur Laufzeit (Dynamic Context Injection).

Implementierte Techniken:
  1. ROLE PROMPTING            -> system_{lang}.txt (Karriere-Coach-Persona)
  2. FEW-SHOT PROMPTING        -> few_shot_{lang}.txt (Vorher/Nachher-Beispiele)
  3. CHAIN-OF-THOUGHT (CoT)    -> chain_of_thought_{lang}.txt (strukturierte Analyse)
"""

from functools import lru_cache
from pathlib import Path
from typing import List

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache(maxsize=None)
def load_template(name: str, language: str) -> str:
    """Lädt eine Prompt-Vorlage, z. B. load_template('system', 'de')."""
    lang = language if language in ("de", "en") else "de"
    return (PROMPTS_DIR / f"{name}_{lang}.txt").read_text(encoding="utf-8").strip()


def system_prompt(language: str) -> str:
    """ROLE PROMPTING — Persona."""
    return load_template("system", language)


def build_user_message(
    *,
    job_description: str,
    wishes: str,
    cv_context: List[str],
    language: str,
    technique: str,
) -> str:
    """Baut die User-Nachricht inkl. Dynamic Context Injection."""
    context = "\n\n---\n".join(cv_context) if cv_context else (
        "(no CV text available)" if language == "en" else "(kein Lebenslauf-Text vorhanden)"
    )

    technique_block = ""
    if technique in ("few_shot", "auto"):
        technique_block += load_template("few_shot", language) + "\n\n"
    if technique in ("chain_of_thought", "auto"):
        technique_block += load_template("chain_of_thought", language) + "\n\n"

    none_wishes = "(none)" if language == "en" else "(keine)"
    return load_template("user_message", language).format(
        job_description=job_description.strip(),
        wishes=wishes.strip() or none_wishes,
        cv_context=context,
        technique_block=technique_block,
        format=load_template("format", language),
    )


def refine_message(instruction: str, language: str) -> str:
    """Folge-Nachricht für iteratives Verfeinern (nutzt Conversation History)."""
    return load_template("refine", language).format(
        instruction=instruction,
        format=load_template("format", language),
    )
