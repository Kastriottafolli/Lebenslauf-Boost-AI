#!/usr/bin/env python3
"""Generiert Architektur- und Schema-PNGs (Sapphire Nightfall) für README & Präsentation."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Sapphire Nightfall
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
PANEL = "#e2eaf6"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def box(draw, x1, y1, x2, y2, title, lines, header_color, subtitle=""):
    rounded_rect(draw, (x1, y1, x2, y2), 12, WHITE, LINE, 2)
    draw.rectangle((x1, y1, x2, y1 + 44), fill=header_color)
    draw.text(((x1 + x2) // 2, y1 + 22), title, anchor="mm", font=font(15, True), fill=WHITE)
    y = y1 + 62
    if subtitle:
        draw.text((x1 + 16, y), subtitle, font=font(11, True), fill=ACCENT2)
        y += 22
    for line in lines:
        draw.ellipse((x1 + 16, y - 5, x1 + 24, y + 3), fill=ACCENT)
        draw.text((x1 + 32, y), line, font=font(12), fill=INK)
        y += 24


def arrow(draw, start, end):
    draw.line((*start, *end), fill=MUTED, width=3)
    ex, ey = end
    draw.polygon([(ex, ey), (ex - 14, ey - 7), (ex - 14, ey + 7)], fill=MUTED)


def make_architecture() -> Image.Image:
    w, h = 1600, 920
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 88), fill=INK)
    draw.text((48, 28), "Architektur — Lebenslauf Boost AI", font=font(26, True), fill=WHITE)
    draw.text((48, 58), "Schichten-Architektur · Router → Service → LLM/DB · Sapphire Nightfall", font=font(14), fill=GOLD)

    box(draw, 40, 120, 340, 460, "frontend/", [
        "index.html · SPA (DE/EN)",
        "css/ — tokens · depth · mascot",
        "js/ui/ — upload · generate · mascot",
        "js/ui/ — steps · exporter · motion",
        "Boosti — geführte Tour",
        "6 Export-Designs · BYOK",
    ], ACCENT, "Vanilla HTML/CSS/JS")

    draw.rounded_rectangle((380, 108, 1200, 668), radius=14, outline=GOLD, width=2)
    draw.text((400, 118), "backend/ — FastAPI", font=font(13, True), fill=ACCENT2)

    box(draw, 400, 148, 1180, 266, "routers/", [
        "system · sessions · documents · generations · exports · frontend",
    ], ACCENT2)

    box(draw, 400, 288, 1180, 436, "services/", [
        "session · document · generation · export · rag · extraction",
        "PDF/DOCX · Foto · RAG · ATS · 6 Export-Designs",
    ], ACCENT)

    box(draw, 400, 458, 760, 648, "llm/", [
        "llm_service — Vergleich · Demo",
        "anthropic_provider · openai_provider",
        "prompts.py → prompts/*.txt",
        "Few-shot · CoT · Dynamic Context",
    ], MUTED)

    box(draw, 780, 458, 1180, 648, "models · schemas · database", [
        "Pydantic-Validierung · SQLAlchemy ORM",
        "SQLite — 4 Tabellen",
        "sessions · cv_documents · generations · messages",
    ], SLATE)

    box(draw, 1220, 148, 1560, 278, "prompts/", [
        "system_*.txt · few_shot_*.txt",
        "chain_of_thought_*.txt · format_*.txt",
        "DE/EN · externe Vorlagen",
    ], GOLD)

    box(draw, 1220, 320, 1560, 480, "Externe KI-APIs", [
        "Anthropic Claude",
        "OpenAI GPT + Embeddings",
        "Keys nur pro Request (BYOK)",
    ], INK)

    for s, e in [((340, 290), (400, 290)), ((790, 266), (790, 288)), ((790, 436), (790, 458)),
                 ((760, 553), (780, 553)), ((590, 553), (1220, 208)), ((990, 553), (1220, 400))]:
        arrow(draw, s, e)

    rounded_rect(draw, (40, 700, 1560, 788), 12, WHITE, LINE, 2)
    draw.text((60, 722), "POST /api/generate", font=font(13, True), fill=ACCENT2)
    draw.text((60, 748), "Validieren → RAG → Prompt → Provider (compare: beide) → ATS → Persistenz → JSON", font=font(12), fill=MUTED)

    box(draw, 40, 820, 340, 900, "static/", ["boosti.svg · logo.svg"], SLATE)
    box(draw, 360, 820, 660, 900, "CI", [".github/workflows — ruff + pytest"], ACCENT2)

    return img


def make_schema() -> Image.Image:
    w, h = 1500, 1280
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    draw.text((60, 36), "Datenbankschema — Lebenslauf Boost AI", font=font(26, True), fill=INK)
    draw.text((60, 68), "SQLite · SQLAlchemy ORM · 4 Tabellen · Quelle: backend/models.py", font=font(13), fill=MUTED)

    def table(x, y, tw, th, name, header, rows):
        rounded_rect(draw, (x, y, x + tw, y + th), 10, WHITE, LINE, 2)
        draw.rectangle((x, y, x + tw, y + 40), fill=header)
        draw.text((x + 14, y + 20), name, anchor="lm", font=font(14, True), fill=WHITE)
        ry = y + 54
        for col, typ in rows:
            draw.line((x, ry - 8, x + tw, ry - 8), fill=LINE)
            draw.text((x + 14, ry), col, font=font(12, True), fill=INK)
            draw.text((x + tw - 14, ry), typ, anchor="rm", font=font(10), fill=FAINT)
            ry += 26

    table(60, 120, 400, 210, "sessions", ACCENT2, [
        ("id", "TEXT(36) PK"),
        ("language", "TEXT(2) de|en"),
        ("job_description", "TEXT"),
        ("wishes", "TEXT"),
        ("created_at", "DATETIME"),
    ])

    table(950, 120, 490, 260, "cv_documents", ACCENT, [
        ("id", "TEXT(36) PK"),
        ("session_id", "FK → sessions UQ"),
        ("filename", "TEXT(255)"),
        ("content", "TEXT"),
        ("index_json", "JSON RAG"),
        ("photo_data_url", "TEXT nullable"),
        ("created_at", "DATETIME"),
    ])

    table(950, 420, 490, 360, "generations", MUTED, [
        ("id", "TEXT(36) PK"),
        ("session_id", "FK → sessions"),
        ("provider", "claude|openai"),
        ("model", "TEXT(64)"),
        ("technique", "auto|few_shot|…"),
        ("content", "TEXT Markdown"),
        ("ats_score", "FLOAT 0–100"),
        ("matched_keywords", "JSON"),
        ("missing_keywords", "JSON"),
        ("is_selected", "BOOLEAN"),
        ("created_at", "DATETIME"),
    ])

    table(950, 820, 490, 210, "messages", SLATE, [
        ("id", "TEXT(36) PK"),
        ("session_id", "FK → sessions"),
        ("role", "user|assistant"),
        ("content", "TEXT"),
        ("created_at", "DATETIME"),
    ])

    # Beziehungen
    draw.line((460, 225, 700, 225, 700, 250, 950, 250), fill=FAINT, width=2)
    draw.line((460, 225, 700, 225, 700, 600, 950, 600), fill=FAINT, width=2)
    draw.line((460, 225, 700, 225, 700, 925, 950, 925), fill=FAINT, width=2)
    draw.text((680, 238), "1:1 UNIQUE", font=font(10, True), fill=ACCENT)
    draw.text((680, 588), "1 : n", font=font(10, True), fill=MUTED)
    draw.text((680, 912), "1 : n", font=font(10, True), fill=SLATE)

    rounded_rect(draw, (60, 360, 460, 560), 10, "#f7fafd", LINE, 2)
    draw.text((78, 388), "Datenfluss", font=font(13, True), fill=INK)
    flows = [
        "POST /api/session → INSERT sessions",
        "POST /api/upload-cv → cv_documents + RAG",
        "POST /api/generate → generations + messages",
        "POST /api/refine → liest messages, schreibt neu",
        "POST /api/export → zustandslos (6 Designs)",
    ]
    y = 418
    for f in flows:
        draw.text((78, y), f, font=font(11), fill=MUTED)
        y += 28

    draw.text((60, 1060), "PRAGMA foreign_keys = ON · ON DELETE CASCADE · UUIDv4 · CHECK-Constraints · API-Keys nie gespeichert (BYOK)", font=font(11), fill=FAINT)
    return img


def main() -> None:
    # SVG-Farben synchron halten
    svg = DOCS / "schema.svg"
    text = svg.read_text(encoding="utf-8")
    for old, new in {"#f7f5f0": BG, "#17130c": INK, "#6d6455": MUTED}.items():
        text = text.replace(old, new)
    svg.write_text(text, encoding="utf-8")

    arch = make_architecture()
    arch.save(DOCS / "architecture.png", optimize=True)
    shutil.copy(DOCS / "architecture.png", DOCS / "video/assets/06-architecture.png")

    schema = make_schema()
    schema.save(DOCS / "schema.png", optimize=True)

    print("✓ docs/architecture.png + architecture.svg")
    print("✓ docs/schema.png + schema.svg (Farben)")


if __name__ == "__main__":
    main()
