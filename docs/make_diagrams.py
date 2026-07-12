#!/usr/bin/env python3
"""Generiert super verständliche Anfänger-Diagramme (Architektur + Datenbank)."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

BG = "#eef3fa"
INK = "#262b40"
MUTED = "#5379ae"
FAINT = "#8ba3c7"
ACCENT = "#0474c4"
ACCENT2 = "#06457f"
SLATE = "#2c444c"
GOLD = "#a8c4ec"
WHITE = "#ffffff"
LINE = "#d5deee"
SOFT = "#f7fafd"
GREEN_BG = "#e2eaf6"
BLUE_BG = "#e2eaf6"
PURPLE_BG = "#f7fafd"
ORANGE_BG = "#f7fafd"


def font(size: int, bold: bool = False):
    paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def rr(draw, box, r, fill, outline=LINE, w=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w)


def badge(draw, x, y, n, color=ACCENT):
    draw.ellipse((x, y, x + 36, y + 36), fill=color)
    draw.text((x + 18, y + 18), str(n), anchor="mm", font=font(16, True), fill=WHITE)


def section_title(draw, y, num, title, subtitle=""):
    badge(draw, 48, y - 6, num, ACCENT2)
    draw.text((96, y + 2), title, font=font(22, True), fill=INK)
    if subtitle:
        draw.text((96, y + 30), subtitle, font=font(13), fill=MUTED)


def step_card(draw, x, y, w, h, num, title, person, api, db, result, color=ACCENT):
    rr(draw, (x, y, x + w, y + h), 12, WHITE)
    badge(draw, x + 14, y + 14, num, color)
    draw.text((x + 60, y + 18), title, font=font(15, True), fill=INK)
    draw.text((x + 60, y + 40), person, font=font(12), fill=MUTED)
    labels = [("Was passiert?", person), ("API-Aufruf", api), ("In der DB", db), ("Ergebnis", result)]
    ly = y + 68
    for label, val in labels:
        draw.text((x + 20, ly), label, font=font(11, True), fill=ACCENT2)
        draw.text((x + 130, ly), val, font=font(11), fill=INK)
        ly += 22


def glossary_box(draw, x, y, w, h, items):
    rr(draw, (x, y, x + w, y + h), 12, SOFT)
    draw.text((x + 16, y + 16), "Mini-Lexikon — Begriffe sofort verstehen", font=font(14, True), fill=INK)
    ly = y + 48
    for term, expl in items:
        draw.text((x + 16, ly), term, font=font(11, True), fill=ACCENT)
        draw.text((x + 100, ly), expl, font=font(11), fill=INK)
        ly += 26


def make_architecture() -> Image.Image:
    w, h = 1800, 2480
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # Header
    d.rectangle((0, 0, w, 130), fill=INK)
    d.text((48, 36), "Architektur — Lebenslauf Boost AI", font=font(30, True), fill=WHITE)
    d.text((48, 76), "So funktioniert die App — Schritt für Schritt, auch ohne Programmierkenntnisse", font=font(15), fill=GOLD)
    d.text((48, 102), "Lese von oben nach unten · Jede Box erklärt genau EINE Aufgabe", font=font(12), fill=FAINT)

    y = 160
    section_title(d, y, 1, "Die wichtigste Idee in 10 Sekunden",
                  "Du benutzt die Webseite → der Server macht die Arbeit → die KI schreibt → du lädst herunter.")
    y += 70
    rr(d, (48, y, w - 48, y + 100), 14, WHITE)
    boxes = [
        ("👤 Du", "Browser\nStellenanzeige + CV", ACCENT),
        ("🖥️ Frontend", "Was du siehst\nBoosti führt dich", ACCENT2),
        ("⚙️ Backend", "Logik + Speicher\nFastAPI Server", MUTED),
        ("🤖 KI", "Claude / OpenAI\nschreibt Entwurf", SLATE),
        ("📄 Datei", "PDF oder Word\n6 Designs", ACCENT),
    ]
    bx = 70
    for title, sub, col in boxes:
        d.rounded_rectangle((bx, y + 16, bx + 300, y + 84), radius=10, fill=col)
        d.text((bx + 150, y + 38), title, anchor="mm", font=font(14, True), fill=WHITE)
        for i, line in enumerate(sub.split("\n")):
            d.text((bx + 150, y + 58 + i * 16), line, anchor="mm", font=font(11), fill=GOLD if i else WHITE)
        if bx < w - 400:
            d.polygon([(bx + 310, y + 50), (bx + 330, y + 42), (bx + 330, y + 58)], fill=FAINT)
        bx += 340
    y += 130

    section_title(d, y, 2, "Dein Weg durch die App — 8 Schritte",
                  "Links: Was DU tust · Rechts: Was der Server im Hintergrund macht")
    y += 60
    steps = [
        ("App öffnen", "Seite laden", "POST /api/session", "Neue Sitzung (UUID) anlegen", "Du bekommst eine anonyme ID", ACCENT2),
        ("CV hochladen", "PDF/Word wählen", "POST /api/upload-cv", "Text + Foto extrahieren, RAG-Index bauen", "Dein Lebenslauf ist durchsuchbar", ACCENT),
        ("Stelle einfügen", "Jobtext + Wünsche", "POST /api/generate (Teil 1)", "sessions.job_description speichern", "Ziel-Stelle ist hinterlegt", ACCENT2),
        ("KI generiert", "«Generieren» klicken", "POST /api/generate", "RAG → Prompt → Claude/OpenAI", "Neuer Lebenslauf-Entwurf", MUTED),
        ("Vergleichen", "Zwei Modelle wählen", "provider=compare", "2× generations + ATS-Score", "Du siehst welcher besser passt", SLATE),
        ("Verfeinern", "«Kürzer» eingeben", "POST /api/refine", "messages lesen + neue generation", "Verbesserte Version, alte bleibt", ACCENT),
        ("Design wählen", "Azure bis Slate", "Frontend only", "Kein DB-Schreiben", "Live-Vorschau rechts", ACCENT2),
        ("Herunterladen", "PDF/Word klicken", "POST /api/export", "ReportLab / python-docx", "Fertige Datei auf deinem PC", ACCENT),
    ]
    for i, (title, person, api, db, result, col) in enumerate(steps):
        row, col_side = divmod(i, 2)
        sx = 48 if col_side == 0 else 930
        sy = y + row * 148
        step_card(d, sx, sy, 820, 132, i + 1, title, person, api, db, result, col)
    y += 4 * 148 + 20

    section_title(d, y, 3, "Die 5 Schichten — wer macht was?",
                  "Jede Schicht hat EINE klare Aufgabe. Oben = nah am Nutzer, unten = Technik.")
    y += 58
    layers = [
        ("① Frontend  frontend/", "Das siehst DU im Browser",
         ["HTML-Seite mit 3 Schritten (Eingabe → Bearbeiten → Design)", "Boosti erklärt jeden Klick mit «Erledigt»-Button",
          "6 Design-Vorschauen · API-Key bleibt nur in deinem Browser (BYOK)", "Sprache DE/EN umschaltbar"], ACCENT),
        ("② Router  backend/routers/", "Empfängt deine Klicks als HTTP-Anfragen",
         ["system.py → Status prüfen", "sessions.py → Sitzung starten", "documents.py → CV hochladen",
          "generations.py → Generieren & Verfeinern", "exports.py → PDF/Word Download"], ACCENT2),
        ("③ Services  backend/services/", "Macht die eigentliche Arbeit",
         ["document_service → PDF lesen, Foto finden", "rag_service → relevante CV-Teile finden",
          "generation_service → KI anstoßen + ATS-Score", "export_service → 6 Designs als PDF/Word"], MUTED),
        ("④ LLM  backend/llm/", "Spricht mit Claude & OpenAI",
         ["Lädt Prompt-Vorlagen aus prompts/", "Few-shot + Chain-of-Thought Techniken",
          "Demo-Modus ohne Key (regelbasiert, klar markiert)", "Vergleichsmodus: beide Anbieter parallel"], SLATE),
        ("⑤ Datenbank  SQLite", "Speichert alles dauerhaft (lokal auf dem Server)",
         ["sessions → deine Stellenanzeige + Wünsche", "cv_documents → Lebenslauf + RAG-Index + Foto",
          "generations → jede KI-Version + Keyword-Score", "messages → Chat-Verlauf für Verfeinerung"], ACCENT2),
    ]
    for title, subtitle, bullets, col in layers:
        rr(d, (48, y, w - 48, y + 118), 12, WHITE)
        d.rectangle((48, y, w - 48, y + 36), fill=col)
        d.text((64, y + 18), title, anchor="lm", font=font(14, True), fill=WHITE)
        d.text((64, y + 52), subtitle, font=font(12, True), fill=ACCENT2)
        ly = y + 74
        for b in bullets:
            d.ellipse((64, ly - 4, 72, ly + 4), fill=ACCENT)
            d.text((82, ly), b, font=font(11), fill=INK)
            ly += 20
        y += 128

    section_title(d, y, 4, "Ein Klick auf «Generieren» — was passiert genau?",
                  "POST /api/generate · in dieser Reihenfolge:")
    y += 58
    flow = [
        "① Pydantic prüft: Ist Stellenanzeige lang genug? Ist CV da?",
        "② RAG holt die 5 relevantesten Absätze aus deinem Lebenslauf",
        "③ Prompt wird gebaut: Rolle + Beispiele + Stellenanzeige + CV-Auszüge",
        "④ Claude und/oder OpenAI schreiben den Lebenslauf (nur echte Fakten!)",
        "⑤ ATS-Analyse: Welche Job-Keywords fehlen noch? Score 0–100 %",
        "⑥ Alles wird gespeichert: generations + messages in SQLite",
        "⑦ JSON-Antwort → Frontend zeigt den Entwurf zum Bearbeiten",
    ]
    rr(d, (48, y, w - 48, y + 200), 12, SOFT)
    ly = y + 24
    for line in flow:
        d.text((64, ly), line, font=font(12), fill=INK)
        ly += 26
    y += 220

    glossary_box(d, 48, y, w - 96, 200, [
        ("Frontend", "Alles was du im Browser siehst und anklickst"),
        ("Backend", "Der unsichtbare Server — rechnet, speichert, ruft KI auf"),
        ("API", "Schnittstelle: Frontend fragt, Backend antwortet (JSON)"),
        ("RAG", "Retrieval: KI liest nur relevante Teile deines CVs, erfindet nichts"),
        ("BYOK", "Bring Your Own Key — dein API-Key bleibt nur im Browser"),
        ("ATS", "Applicant Tracking System — prüft ob Job-Keywords im CV stehen"),
        ("Router → Service", "Router nimmt Anfrage entgegen, Service macht die Arbeit"),
    ])
    y += 220

    d.text((48, y), "Ordner: frontend/ · backend/ · prompts/ · static/ · docs/  |  CI: GitHub Actions (Tests)",
           font=font(11), fill=FAINT)
    return img


def make_schema() -> Image.Image:
    w, h = 1800, 2680
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    d.rectangle((0, 0, w, 130), fill=INK)
    d.text((48, 36), "Datenbank — Lebenslauf Boost AI", font=font(30, True), fill=WHITE)
    d.text((48, 76), "Wo und wie deine Daten gespeichert werden — Schritt für Schritt erklärt", font=font(15), fill=GOLD)
    d.text((48, 102), "SQLite = kleine Datei auf dem Server · 4 Tabellen · keine API-Keys gespeichert!", font=font(12), fill=FAINT)

    y = 160
    section_title(d, y, 1, "Stell dir einen Bewerbungsordner vor",
                  "sessions = der Ordner mit deiner Bewerbung. Die anderen Tabellen = Inhalt darin.")
    y += 58
    rr(d, (48, y, w - 48, y + 110), 14, WHITE)
    folders = [
        ("📁 sessions", "Der Ordner\n(zentral)", ACCENT2),
        ("📄 cv_documents", "Dein Original-\nLebenslauf", ACCENT),
        ("✨ generations", "Alle KI-\nVersionen", MUTED),
        ("💬 messages", "Chat für\nVerfeinerung", SLATE),
    ]
    fx = 70
    for title, sub, col in folders:
        d.rounded_rectangle((fx, y + 16, fx + 380, y + 90), radius=10, fill=col)
        d.text((fx + 20, y + 34), title, font=font(13, True), fill=WHITE)
        for i, line in enumerate(sub.split("\n")):
            d.text((fx + 20, y + 56 + i * 16), line, font=font(11), fill=GOLD)
        if fx < 1400:
            d.text((fx + 395, y + 52), "→", font=font(20, True), fill=FAINT)
        fx += 420
    y += 140

    section_title(d, y, 2, "Der komplette Ablauf — 8 Schritte in der Datenbank",
                  "Jede Zeile: Was DU machst → Welcher API-Aufruf → Was in der DB passiert")
    y += 58
    db_steps = [
        ("App öffnen", "POST /api/session", "INSERT in sessions", "Neue UUID — deine anonyme Sitzungs-ID"),
        ("CV hochladen", "POST /api/upload-cv", "INSERT in cv_documents (+ RAG-Index)", "Text, Suchindex und optionales Foto"),
        ("Stelle + Wünsche", "POST /api/generate", "UPDATE sessions", "job_description und wishes gespeichert"),
        ("RAG sucht", "(intern)", "READ cv_documents.index_json", "Top-5 passende CV-Absätze für die KI"),
        ("KI schreibt", "POST /api/generate", "INSERT generations + messages", "Neuer Entwurf + ATS-Score + Chat"),
        ("Verfeinern", "POST /api/refine", "READ messages, INSERT neu", "Alte Version bleibt — neue kommt dazu"),
        ("Design wählen", "(nur Browser)", "— nichts in DB —", "Nur Vorschau, kein Speichern nötig"),
        ("Download", "POST /api/export", "— nichts in DB —", "PDF/Word wird direkt erzeugt & gesendet"),
    ]
    for i, (action, api, db, result) in enumerate(db_steps):
        row, side = divmod(i, 2)
        sx = 48 if side == 0 else 930
        sy = y + row * 130
        rr(d, (sx, sy, sx + 820, sy + 118), 12, WHITE)
        badge(d, sx + 14, sy + 14, i + 1)
        d.text((sx + 60, sy + 18), action, font=font(14, True), fill=INK)
        for label, val, ly in [("API", api, sy + 44), ("DB", db, sy + 66), ("→", result, sy + 88)]:
            d.text((sx + 20, ly), label, font=font(10, True), fill=ACCENT2)
            d.text((sx + 60, ly), val, font=font(10), fill=INK)
    y += 4 * 130 + 30

    section_title(d, y, 3, "Wie die Tabellen zusammenhängen",
                  "session_id = der Klebstoff. Alles gehört zu EINER Bewerbung.")
    y += 58
    rr(d, (48, y, w - 48, y + 180), 14, WHITE)
    d.rounded_rectangle((70, y + 50, 400, y + 140), radius=10, fill=ACCENT2)
    d.text((235, y + 78), "sessions", anchor="mm", font=font(16, True), fill=WHITE)
    d.text((235, y + 102), "id = S-100", anchor="mm", font=font(12), fill=GOLD)
    d.text((235, y + 122), "1 Bewerbung", anchor="mm", font=font(11), fill=GOLD)
    rels = [
        (480, y + 40, "cv_documents", "1 : 1  (max. 1 CV pro Sitzung)", ACCENT),
        (480, y + 90, "generations", "1 : n  (viele KI-Versionen)", MUTED),
        (480, y + 140, "messages", "1 : n  (viele Chat-Nachrichten)", SLATE),
    ]
    for rx, ry, name, rel, col in rels:
        d.polygon([(420, ry + 20), (460, ry + 12), (460, ry + 28)], fill=FAINT)
        d.rounded_rectangle((480, ry, 900, ry + 50), radius=8, fill=col)
        d.text((500, ry + 16), name, font=font(13, True), fill=WHITE)
        d.text((500, ry + 34), rel, font=font(10), fill=GOLD)
    rules = [
        "FK = Fremdschlüssel: Kind darf nur existieren wenn Eltern-Session existiert",
        "CASCADE = Session löschen → alle Kind-Daten werden automatisch mitgelöscht",
        "UNIQUE auf cv_documents.session_id = nie zwei CVs gleichzeitig",
        "INDEX auf session_id = schnelles Laden aller Daten einer Bewerbung",
    ]
    ry = y + 30
    for rule in rules:
        d.text((950, ry), "✓ " + rule, font=font(11), fill=INK)
        ry += 28
    y += 200

    section_title(d, y, 4, "Alle Felder — technischer Name + einfache Bedeutung",
                  "Nichts ausgelassen. Quelle: backend/models.py")
    y += 58

    def field_table(x, ty, tw, th, name, header, fields, note=""):
        rr(d, (x, ty, x + tw, ty + th), 12, WHITE)
        d.rectangle((x, ty, x + tw, ty + 40), fill=header)
        d.text((x + 16, ty + 20), name, anchor="lm", font=font(14, True), fill=WHITE)
        ly = ty + 54
        for fname, rule, meaning in fields:
            d.line((x + 12, ly - 6, x + tw - 12, ly - 6), fill=LINE)
            d.text((x + 16, ly), fname, font=font(11, True), fill=INK)
            d.text((x + 200, ly), rule, font=font(9), fill=FAINT)
            d.text((x + 420, ly), meaning, font=font(10), fill=MUTED)
            ly += 24
        if note:
            d.rounded_rectangle((x + 12, ty + th - 28, x + tw - 12, ty + th - 8), radius=4, fill=GREEN_BG)
            d.text((x + 20, ty + th - 16), note, font=font(9), fill=ACCENT2)

    field_table(48, y, 820, 200, "sessions — 5 Felder (dein Bewerbungsordner)", ACCENT2, [
        ("id", "TEXT PK · UUID", "Eindeutige Sitzungsnummer (nicht erratbar)"),
        ("language", "de | en", "Sprache der App und KI-Ausgabe"),
        ("job_description", "TEXT", "Die komplette Stellenanzeige"),
        ("wishes", "TEXT", "Deine optionalen Wünsche (Ton, Länge…)"),
        ("created_at", "DATETIME", "Wann die Sitzung gestartet wurde"),
    ], "Wird bei /api/session angelegt, bei /api/generate aktualisiert")

    field_table(930, y, 820, 260, "cv_documents — 7 Felder (dein Lebenslauf)", ACCENT, [
        ("id", "TEXT PK", "Dokument-ID"),
        ("session_id", "FK · UNIQUE", "Gehört zu genau EINER Sitzung"),
        ("filename", "TEXT(255)", "Original-Dateiname z.B. Lebenslauf.pdf"),
        ("content", "TEXT", "Extrahierter Volltext aus PDF/Word"),
        ("index_json", "JSON", "RAG: Text-Chunks + Embeddings für Suche"),
        ("photo_data_url", "TEXT · NULL", "Bewerbungsfoto als Base64 (optional)"),
        ("created_at", "DATETIME", "Upload-Zeitpunkt"),
    ], "Neuer Upload ersetzt den alten Datensatz")

    y += 280
    field_table(48, y, 1050, 320, "generations — 11 Felder (jede KI-Version)", MUTED, [
        ("id", "TEXT PK", "Versions-ID"),
        ("session_id", "FK · INDEX", "Zu welcher Bewerbung"),
        ("provider", "claude | openai", "Welcher KI-Anbieter"),
        ("model", "TEXT", "z.B. gpt-4o-mini oder demo"),
        ("technique", "auto | few_shot | …", "Prompt-Methode"),
        ("content", "TEXT Markdown", "Der optimierte Lebenslauf"),
        ("ats_score", "FLOAT 0–100", "Keyword-Abdeckung in Prozent"),
        ("matched_keywords", "JSON Array", "Gefundene Job-Begriffe"),
        ("missing_keywords", "JSON Array", "Noch fehlende Begriffe"),
        ("is_selected", "BOOLEAN", "Reserviert: Favorit markieren"),
        ("created_at", "DATETIME", "Wann diese Version erstellt wurde"),
    ], "Vergleichsmodus = 2 Zeilen (Claude + OpenAI). Nichts wird überschrieben!")

    field_table(1180, y, 570, 200, "messages — 5 Felder (Chat)", SLATE, [
        ("id", "TEXT PK", "Nachrichten-ID"),
        ("session_id", "FK · INDEX", "Zugehörige Sitzung"),
        ("role", "user | assistant", "Wer hat geschrieben"),
        ("content", "TEXT", "Anweisung oder KI-Antwort"),
        ("created_at", "DATETIME", "Reihenfolge im Chat"),
    ])

    field_table(1180, y + 220, 570, 100, "JSON kurz erklärt", ACCENT2, [
        ("index_json", "chunks + embeddings", "null = offline TF-IDF Fallback"),
        ("matched_keywords", '["python","sql"]', "Was die Stelle verlangt und im CV steht"),
        ("missing_keywords", '["docker"]', "Was noch fehlt für besseren ATS-Score"),
    ])
    y += 540

    glossary_box(d, 48, y, 820, 220, [
        ("PK (Primärschlüssel)", "Eindeutige ID — jede Zeile hat genau eine"),
        ("FK (Fremdschlüssel)", "Verweis auf id einer anderen Tabelle"),
        ("1 : 1", "Links max. ein Datensatz rechts (z.B. ein CV pro Session)"),
        ("1 : n", "Links viele Datensätze rechts (z.B. viele KI-Versionen)"),
        ("UUID", "Zufällige 36-Zeichen-ID — sicher und nicht erratbar"),
        ("BYOK", "API-Keys werden NIE in der DB gespeichert — nur im Browser"),
    ])

    rr(d, (930, y, w - 48, y + 220), 12, WHITE, GOLD, 2)
    d.text((950, y + 20), "Sicherheit & Regeln", font=font(14, True), fill=INK)
    safety = [
        "PRAGMA foreign_keys = ON — ungültige Verweise werden abgelehnt",
        "ON DELETE CASCADE — Session löschen = alles dazu weg",
        "CHECK-Constraints — nur erlaubte Werte (de/en, claude/openai…)",
        "Keine erfundenen Fakten — KI darf nur RAG-Daten aus deinem CV nutzen",
        "Export ist zustandslos — 6 Designs (Azure…Slate), nichts wird gespeichert",
    ]
    sy = y + 52
    for s in safety:
        d.text((950, sy), "🔒 " + s, font=font(11), fill=INK)
        sy += 32

    d.text((48, h - 30), "Quelle: backend/models.py · DDL: docs/schema.sql · Ausführlich: docs/DATABASE.md",
           font=font(11), fill=FAINT)
    return img


def sync_schema_svg_colors() -> None:
    """schema.svg an Sapphire-Palette anpassen (falls vorhanden)."""
    svg = DOCS / "schema.svg"
    if not svg.exists():
        return
    text = svg.read_text(encoding="utf-8")
    repl = {
        "#f7f5f0": BG, "#17130c": INK, "#6d6455": MUTED, "#9a8f7c": FAINT,
        "#C98A00": ACCENT, "#A06A24": ACCENT2, "#106B52": ACCENT, "#5B4A8F": MUTED,
        "#A85B14": SLATE, "#2563eb": ACCENT, "#172033": INK, "#f8fafc": BG,
    }
    for old, new in repl.items():
        text = text.replace(old, new)
    svg.write_text(text, encoding="utf-8")


def main() -> None:
    sync_schema_svg_colors()
    # schema-extended als Referenz-SVG für GitHub (skalierbar)
    ext = DOCS / "schema-extended.svg"
    if ext.exists():
        text = ext.read_text(encoding="utf-8")
        for old, new in {"#2563eb": ACCENT, "#172033": INK, "#f8fafc": BG, "#2f855a": ACCENT2,
                         "#3b73b9": ACCENT, "#7355a0": MUTED, "#b5651d": SLATE}.items():
            text = text.replace(old, new)
        (DOCS / "schema.svg").write_text(text, encoding="utf-8")

    arch = make_architecture()
    arch.save(DOCS / "architecture.png", optimize=True)
    shutil.copy(DOCS / "architecture.png", DOCS / "video/assets/06-architecture.png")

    schema = make_schema()
    schema.save(DOCS / "schema.png", optimize=True)

    print("✓ docs/architecture.png  (Anfänger-Infografik, 1800×2480)")
    print("✓ docs/schema.png        (Anfänger-Infografik, 1800×2680)")
    print("✓ docs/schema.svg        (Erweitertes SVG aktualisiert)")


if __name__ == "__main__":
    main()
