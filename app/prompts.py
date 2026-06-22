"""Prompt Engineering.

Implementierte Techniken (klar getrennt und auswählbar):
  1. FEW-SHOT PROMPTING        -> konkrete Vorher/Nachher-Beispiele im Prompt.
  2. CHAIN-OF-THOUGHT (CoT)    -> das Modell analysiert erst strukturiert die Lücke
                                  zwischen Lebenslauf und Stelle, bevor es schreibt.
  + ROLE PROMPTING            -> System-Persona als erfahrene/r Karriere-Coach/HR-Profi.

Dynamic Context Injection: Stellenbeschreibung, Wünsche und die per RAG abgerufenen
relevanten Lebenslauf-Abschnitte werden zur Laufzeit in den Prompt eingefügt.
"""

from typing import List

# Einheitliches Ausgabeformat, das der Export (PDF/DOCX) zuverlässig parst.
_FORMAT_DE = """\
Gib den Lebenslauf in GENAU diesem Markdown-Format aus (keine Code-Blöcke):

# Vor- und Nachname
Berufsbezeichnung / Zielposition
E-Mail | Telefon | Ort | LinkedIn (nur vorhandene Angaben)

## Profil
2–4 Sätze, zugeschnitten auf die Stelle.

## Berufserfahrung
### Position — Firma (Zeitraum)
- Wirkungsorientierter Bulletpoint mit Ergebnis/Kennzahl
- Weiterer Bulletpoint

## Ausbildung
### Abschluss — Institution (Zeitraum)

## Fähigkeiten
- Kompetenz, Kompetenz, Kompetenz

## Sprachen
- Sprache (Niveau)

Regeln:
- Erfinde KEINE Fakten, Arbeitgeber, Abschlüsse oder Zahlen, die nicht im Lebenslauf stehen.
- Formuliere vorhandene Inhalte stärker und auf die Stelle ausgerichtet.
- Nutze relevante Schlüsselbegriffe der Stellenanzeige, wo sie zur Erfahrung passen.
- Antworte ausschließlich mit dem Lebenslauf im obigen Format."""

_FORMAT_EN = """\
Return the CV in EXACTLY this Markdown format (no code fences):

# First and Last Name
Job title / target role
Email | Phone | Location | LinkedIn (only what is available)

## Summary
2–4 sentences tailored to the role.

## Experience
### Title — Company (dates)
- Impact-oriented bullet with a result/metric
- Another bullet

## Education
### Degree — Institution (dates)

## Skills
- Skill, Skill, Skill

## Languages
- Language (level)

Rules:
- Do NOT invent facts, employers, degrees or numbers that are not in the CV.
- Strengthen and re-frame existing content toward the role.
- Weave in relevant keywords from the job posting where they fit the experience.
- Respond with the CV only, in the format above."""


def system_prompt(language: str) -> str:
    """ROLE PROMPTING — Persona."""
    if language == "en":
        return (
            "You are a senior career coach and professional resume writer with 15+ "
            "years of experience and deep knowledge of Applicant Tracking Systems (ATS). "
            "You rewrite CVs to be concise, achievement-driven and perfectly aligned to a "
            "specific job posting, while staying strictly truthful to the candidate's data."
        )
    return (
        "Du bist ein erfahrener Karriere-Coach und professioneller Bewerbungsschreiber "
        "mit über 15 Jahren Erfahrung und tiefem Wissen über Bewerbermanagementsysteme "
        "(ATS). Du formulierst Lebensläufe prägnant, ergebnisorientiert und exakt passend "
        "zur jeweiligen Stelle – und bleibst dabei strikt bei den Fakten der Bewerber:in."
    )


def _few_shot_block(language: str) -> str:
    """FEW-SHOT PROMPTING — Vorher/Nachher-Beispiele."""
    if language == "en":
        return (
            "Here are examples of how to strengthen bullet points "
            "(weak -> strong):\n"
            "- 'Responsible for sales' -> 'Grew regional B2B sales 27% YoY by "
            "restructuring the outbound pipeline and coaching 4 reps.'\n"
            "- 'Helped with the website' -> 'Shipped a React redesign that cut page "
            "load time 40% and lifted sign-up conversion 12%.'\n"
            "- 'Did customer support' -> 'Resolved 60+ tickets/week at a 4.9/5 CSAT, "
            "and wrote a help-center FAQ that reduced repeat tickets 18%.'\n"
        )
    return (
        "Hier sind Beispiele, wie Bulletpoints gestärkt werden "
        "(schwach -> stark):\n"
        "- 'Zuständig für den Vertrieb' -> 'Steigerte den regionalen B2B-Umsatz um "
        "27% p.a. durch Neuaufbau der Outbound-Pipeline und Coaching von 4 "
        "Mitarbeitenden.'\n"
        "- 'Bei der Website geholfen' -> 'Lieferte ein React-Redesign aus, das die "
        "Ladezeit um 40% senkte und die Registrierungs-Conversion um 12% erhöhte.'\n"
        "- 'Kundensupport gemacht' -> 'Löste 60+ Tickets/Woche bei 4,9/5 CSAT und "
        "erstellte eine Hilfe-FAQ, die Wiederholungsanfragen um 18% reduzierte.'\n"
    )


def _cot_block(language: str) -> str:
    """CHAIN-OF-THOUGHT — internes, strukturiertes Vorgehen."""
    if language == "en":
        return (
            "Think step by step internally before writing (do NOT output these steps):\n"
            "1. Extract the key requirements, must-have skills and keywords from the job.\n"
            "2. Map the candidate's real experience to each requirement.\n"
            "3. Identify which true strengths to foreground and how to phrase them.\n"
            "Then output only the final CV.\n"
        )
    return (
        "Gehe vor dem Schreiben gedanklich Schritt für Schritt vor "
        "(diese Schritte NICHT ausgeben):\n"
        "1. Extrahiere die Kernanforderungen, Must-have-Skills und Keywords der Stelle.\n"
        "2. Ordne die echte Erfahrung der Bewerber:in jeder Anforderung zu.\n"
        "3. Entscheide, welche echten Stärken du in den Vordergrund stellst und wie.\n"
        "Gib anschließend nur den fertigen Lebenslauf aus.\n"
    )


def build_user_message(
    *,
    job_description: str,
    wishes: str,
    cv_context: List[str],
    language: str,
    technique: str,
) -> str:
    """Baut die User-Nachricht inkl. Dynamic Context Injection."""
    fmt = _FORMAT_EN if language == "en" else _FORMAT_DE
    context = "\n\n---\n".join(cv_context) if cv_context else (
        "(no CV text available)" if language == "en" else "(kein Lebenslauf-Text vorhanden)"
    )

    if language == "en":
        head = "Create an optimized, ATS-friendly CV tailored to the job below."
        labels = ("JOB POSTING", "CANDIDATE WISHES (optional)", "RELEVANT CV EXCERPTS (RAG)")
        none_wishes = "(none)"
    else:
        head = (
            "Erstelle einen optimierten, ATS-freundlichen Lebenslauf, "
            "zugeschnitten auf die folgende Stelle."
        )
        labels = ("STELLENANZEIGE", "WÜNSCHE DER BEWERBER:IN (optional)", "RELEVANTE LEBENSLAUF-AUSZÜGE (RAG)")
        none_wishes = "(keine)"

    technique_block = ""
    if technique in ("few_shot", "auto"):
        technique_block += _few_shot_block(language) + "\n"
    if technique in ("chain_of_thought", "auto"):
        technique_block += _cot_block(language) + "\n"

    return (
        f"{head}\n\n"
        f"### {labels[0]}\n{job_description.strip()}\n\n"
        f"### {labels[1]}\n{wishes.strip() or none_wishes}\n\n"
        f"### {labels[2]}\n{context}\n\n"
        f"{technique_block}\n"
        f"{fmt}"
    )


def refine_message(instruction: str, language: str) -> str:
    """Folge-Nachricht für iteratives Verfeinern (nutzt Conversation History)."""
    fmt = _FORMAT_EN if language == "en" else _FORMAT_DE
    if language == "en":
        return (
            f"Revise the previous CV according to this instruction: \"{instruction}\".\n"
            f"Keep everything truthful. Return the full updated CV.\n\n{fmt}"
        )
    return (
        f"Überarbeite den vorherigen Lebenslauf gemäß dieser Anweisung: "
        f"\"{instruction}\".\nBleibe bei den Fakten. Gib den vollständigen, "
        f"aktualisierten Lebenslauf zurück.\n\n{fmt}"
    )
