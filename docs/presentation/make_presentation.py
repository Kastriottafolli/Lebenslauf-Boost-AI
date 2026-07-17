"""Erzeugt eine professionelle 5-seitige Projektpraesentation.

Ausgaben:
- lebenslauf-boost-ai-praesentation.pptx
- lebenslauf-boost-ai-praesentation.pdf
- slides/slide-01.png ... slide-05.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.util import Inches
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "presentation"
SLIDES = OUT / "slides"
ASSETS = ROOT / "docs" / "video" / "assets"
W, H = 1920, 1080

BG = "#0d0c12"
SURFACE = "#17161d"
SURFACE_2 = "#201d24"
TEXT = "#f6f0e7"
MUTED = "#aaa4a0"
GOLD = "#e8b866"
GREEN = "#4e9a75"
PURPLE = "#7960a4"
BLUE = "#4f7daf"
ORANGE = "#b56b34"
LINE = "#3b3540"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Helvetica.ttc"),
    ]
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    for y in range(H):
        ratio = y / H
        draw.line((0, y, W, y), fill=(13 + int(7 * ratio), 12 + int(12 * ratio), 18 + int(18 * ratio)))
    draw.ellipse((-420, 480, 550, 1450), fill="#21180f")
    draw.ellipse((1400, -420, 2300, 480), fill="#1c162e")
    return image, draw


def wrap(draw: ImageDraw.ImageDraw, text: str, selected_font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=selected_font) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def text_block(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    size: int,
    color: str = TEXT,
    bold: bool = False,
    width: int = 800,
    spacing: int = 10,
) -> int:
    selected = font(size, bold)
    x, y = xy
    for line in wrap(draw, text, selected, width):
        draw.text((x, y), line, font=selected, fill=color)
        y += size + spacing
    return y


def section_label(draw: ImageDraw.ImageDraw, text: str, page: int) -> None:
    draw.rounded_rectangle((78, 58, 300, 98), radius=20, fill="#2a241d", outline="#6f5836")
    draw.text((189, 78), text.upper(), anchor="mm", font=font(17, True), fill=GOLD)
    draw.text((1830, 62), f"0{page}", anchor="ra", font=font(18, True), fill="#736c73")


def title(draw: ImageDraw.ImageDraw, heading: str, subheading: str = "") -> None:
    draw.text((78, 132), heading, font=font(46, True), fill=TEXT)
    if subheading:
        draw.text((80, 194), subheading, font=font(21), fill=MUTED)


def footer(draw: ImageDraw.ImageDraw) -> None:
    draw.line((78, 1020, 1842, 1020), fill=LINE, width=2)
    draw.text((78, 1042), "LEBENSLAUF BOOST AI", font=font(13, True), fill="#746c68")
    draw.text((1842, 1042), "FastAPI · SQLite · Claude + OpenAI · RAG", anchor="ra", font=font(13), fill="#746c68")


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, color: str = GOLD) -> int:
    selected = font(16, True)
    width = int(draw.textlength(label, font=selected)) + 34
    draw.rounded_rectangle((x, y, x + width, y + 38), radius=19, fill=SURFACE_2, outline=color)
    draw.text((x + width // 2, y + 19), label, anchor="mm", font=selected, fill=color)
    return width


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, outline: str = LINE, fill: str = SURFACE) -> None:
    draw.rounded_rectangle(box, radius=22, fill=fill, outline=outline, width=2)


def bullet_list(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    items: list[str],
    *,
    width: int,
    color: str = GOLD,
    size: int = 21,
    gap: int = 22,
) -> int:
    selected = font(size)
    for item in items:
        lines = wrap(draw, item, selected, width - 42)
        draw.ellipse((x, y + 8, x + 11, y + 19), fill=color)
        line_y = y
        for line in lines:
            draw.text((x + 30, line_y), line, font=selected, fill="#d8d3cd")
            line_y += size + 8
        y = line_y + gap
    return y


def fit_image(source: Path, target: Image.Image, box: tuple[int, int, int, int], *, crop: bool = False) -> None:
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    with Image.open(source).convert("RGB") as image:
        if crop:
            ratio = max(width / image.width, height / image.height)
            image = image.resize((int(image.width * ratio), int(image.height * ratio)), Image.Resampling.LANCZOS)
            left = (image.width - width) // 2
            top = (image.height - height) // 2
            image = image.crop((left, top, left + width, top + height))
        else:
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
            frame = Image.new("RGB", (width, height), "#0a090d")
            frame.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
            image = frame
        target.paste(image, (x1, y1))


def slide_1() -> Image.Image:
    image, draw = base()
    section_label(draw, "Projektpräsentation", 1)
    draw.text((90, 235), "Lebenslauf", font=font(82, True), fill=TEXT)
    draw.text((90, 325), "Boost AI", font=font(92, True), fill=GOLD)
    text_block(
        draw,
        (96, 455),
        "KI-gestützte Lebenslauf-Optimierung – Sapphire Nightfall Design, Boosti-Tour, RAG, Modellvergleich und sechs Export-Designs. Ohne erfundene Fakten.",
        size=28,
        color="#cbc5bf",
        width=760,
        spacing=14,
    )
    x = 96
    for label in ["Boosti", "RAG", "2 KI-Anbieter", "6 Designs"]:
        x += pill(draw, x, 650, label) + 14
    draw.rounded_rectangle((930, 165, 1820, 890), radius=28, fill="#211d1b", outline="#6e593b", width=3)
    fit_image(ASSETS / "01-hero.png", image, (950, 185, 1800, 870), crop=True)
    draw.rounded_rectangle((1120, 835, 1630, 892), radius=28, fill="#2a241d", outline=GOLD)
    draw.text((1375, 864), "Dein CV. Deine Fakten. Professionell formuliert.", anchor="mm", font=font(17, True), fill=GOLD)
    footer(draw)
    return image


def slide_2() -> Image.Image:
    image, draw = base()
    section_label(draw, "Problem & Lösung", 2)
    title(draw, "Warum dieses Projekt?", "Bewerbungen sind individuell – Lebensläufe meistens nicht.")

    card(draw, (78, 255, 705, 840), outline="#7c4b46")
    draw.text((112, 292), "Das Problem", font=font(30, True), fill="#e7a49c")
    bullet_list(
        draw, 115, 355,
        [
            "Jede Stellenanzeige verlangt andere Schwerpunkte und Keywords.",
            "Manuelle Anpassung kostet Zeit und ist fehleranfällig.",
            "Generative KI kann Fähigkeiten oder Erfolge erfinden.",
            "Viele Lebensläufe werden von ATS-Systemen vorgefiltert.",
        ],
        width=540,
        color="#d97f75",
        size=22,
    )

    draw.line((735, 548, 835, 548), fill=GOLD, width=5)
    draw.polygon([(835, 548), (810, 534), (810, 562)], fill=GOLD)

    card(draw, (865, 255, 1740, 840), outline=GREEN)
    draw.text((900, 292), "Die Lösung", font=font(30, True), fill="#86d5aa")
    bullet_list(
        draw, 903, 355,
        [
            "Lebenslauf und Stellenanzeige werden gemeinsam analysiert.",
            "RAG liefert nur relevante, belegte CV-Inhalte an die KI.",
            "Professionelle Prompts steuern Claude und OpenAI.",
            "ATS-Keyword-Check und 5-Sekunden-Ladeübergänge.",
            "Verfeinern, sechs Designs wählen und als PDF/Word exportieren.",
        ],
        width=760,
        color=GREEN,
        size=22,
        gap=15,
    )
    draw.rounded_rectangle((930, 748, 1675, 806), radius=14, fill="#173125")
    draw.text((1302, 777), "Grundregel: Keine Angabe wird ohne Beleg ergänzt.", anchor="mm", font=font(20, True), fill="#98ddb8")
    footer(draw)
    return image


def slide_3() -> Image.Image:
    image, draw = base()
    section_label(draw, "Workflow", 3)
    title(draw, "Vom Upload zum fertigen Lebenslauf", "Ein durchgängiger, nachvollziehbarer Prozess in drei UI-Schritten.")

    screenshots = [
        (ASSETS / "02-input-upload.png", "1", "Eingabe & Upload", "Stelle + CV · Key-Links · RAG"),
        (ASSETS / "03-compare-output.png", "2", "Vergleichen & Bearbeiten", "2 Modelle · ATS · Refine"),
        (ASSETS / "05-design-export.png", "3", "Design & Download", "6 Designs · PDF oder Word"),
    ]
    x_positions = [78, 662, 1246]
    for (source, number, heading, description), x in zip(screenshots, x_positions):
        card(draw, (x, 260, x + 510, 875), outline="#574b3d")
        draw.ellipse((x + 22, 280, x + 70, 328), fill=GOLD)
        draw.text((x + 46, 304), number, anchor="mm", font=font(21, True), fill="#21180f")
        draw.text((x + 85, 283), heading, font=font(23, True), fill=TEXT)
        draw.text((x + 85, 316), description, font=font(15), fill=MUTED)
        draw.rounded_rectangle((x + 20, 355, x + 490, 825), radius=14, fill="#09080b", outline="#39333b")
        fit_image(source, image, (x + 24, 359, x + 486, 821), crop=True)
        if x != x_positions[-1]:
            draw.line((x + 520, 567, x + 565, 567), fill=GOLD, width=4)
            draw.polygon([(x + 565, 567), (x + 548, 557), (x + 548, 577)], fill=GOLD)

    draw.text((78, 922), "Pipeline:", font=font(19, True), fill=GOLD)
    pipeline = "Upload  →  Text & Foto  →  Retrieval  →  Prompt  →  2 Entwürfe  →  ATS  →  Refine  →  Export"
    draw.text((190, 922), pipeline, font=font(19), fill="#d5d0ca")
    footer(draw)
    return image


def slide_4() -> Image.Image:
    image, draw = base()
    section_label(draw, "Technik", 4)
    title(draw, "Architektur und Datenmodell", "Modular aufgebaut, sauber getrennt und vollständig dokumentiert.")

    card(draw, (78, 250, 975, 900), outline=PURPLE)
    draw.text((110, 282), "Anwendungsarchitektur", font=font(26, True), fill="#b9a6dc")
    fit_image(ASSETS / "06-architecture.png", image, (100, 335, 953, 870), crop=False)

    card(draw, (1005, 250, 1740, 900), outline=GREEN)
    draw.text((1037, 282), "SQLite + SQLAlchemy", font=font(26, True), fill="#91d4af")
    fit_image(ROOT / "docs" / "schema.png", image, (1027, 335, 1718, 870), crop=False)

    labels = [
        ("Frontend", "Sapphire · Boosti · DE/EN"),
        ("Backend", "FastAPI · Pydantic"),
        ("KI", "Prompts · Claude · OpenAI"),
        ("Persistenz", "4 Tabellen · Versionen"),
    ]
    x = 90
    for heading, detail in labels:
        draw.rounded_rectangle((x, 930, x + 400, 992), radius=14, fill=SURFACE_2, outline=LINE)
        draw.text((x + 20, 950), heading, font=font(16, True), fill=GOLD)
        draw.text((x + 130, 950), detail, font=font(15), fill="#c4beb8")
        x += 430
    footer(draw)
    return image


def slide_5() -> Image.Image:
    image, draw = base()
    section_label(draw, "Fazit", 5)
    title(draw, "Ergebnis und nächste Schritte", "Ein vollständiger KI-Engineering-Workflow als funktionsfähiger MVP.")

    columns = [
        (
            "Erfüllt",
            PURPLE,
            ["2 Text-APIs", "Professionelle Prompt-Vorlagen", "RAG & Kontextinjektion", "Conversation History", "ATS-Vergleichsanalyse"],
        ),
        (
            "Sicher",
            GREEN,
            ["BYOK + Key-Links Anthropic/OpenAI", "Keine erfundenen Fakten", "Demo-Modus ohne Kosten", "5s Ladeübergänge", "Kaskadierendes Löschen"],
        ),
        (
            "Roadmap",
            ORANGE,
            ["PostgreSQL + Alembic", "Login & Nutzerkonten", "Versions-Rollback", "Anschreiben-Generator", "Tests & Docker"],
        ),
    ]
    x = 78
    for heading, color, items in columns:
        card(draw, (x, 265, x + 535, 765), outline=color)
        draw.rectangle((x, 265, x + 535, 340), fill=color)
        draw.text((x + 267, 303), heading, anchor="mm", font=font(28, True), fill="#fff")
        bullet_list(draw, x + 34, 385, items, width=455, color=color, size=20, gap=18)
        x += 574

    draw.rounded_rectangle((180, 820, 1640, 950), radius=24, fill="#2a241d", outline=GOLD, width=3)
    draw.text(
        (910, 858),
        "Lebenslauf Boost AI verbindet reale Nutzerdaten mit kontrollierter generativer KI.",
        anchor="ma",
        font=font(27, True),
        fill=TEXT,
    )
    draw.text(
        (910, 908),
        "Relevant finden · transparent vergleichen · gezielt verbessern · professionell exportieren",
        anchor="ma",
        font=font(21),
        fill=GOLD,
    )
    footer(draw)
    return image


def save_pptx(slide_paths: list[Path], destination: Path) -> None:
    presentation = Presentation()
    presentation.slide_width = Inches(13.333333)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]
    for path in slide_paths:
        slide = presentation.slides.add_slide(blank)
        slide.shapes.add_picture(
            str(path),
            0,
            0,
            width=presentation.slide_width,
            height=presentation.slide_height,
        )
    presentation.save(destination)


def save_pdf(slide_paths: list[Path], destination: Path) -> None:
    page = landscape((540, 960))
    pdf = canvas.Canvas(str(destination), pagesize=page)
    for path in slide_paths:
        pdf.drawImage(str(path), 0, 0, width=960, height=540)
        pdf.showPage()
    pdf.save()


def main() -> None:
    SLIDES.mkdir(parents=True, exist_ok=True)
    renderers = [slide_1, slide_2, slide_3, slide_4, slide_5]
    paths: list[Path] = []
    for index, renderer in enumerate(renderers, 1):
        path = SLIDES / f"slide-{index:02d}.png"
        renderer().save(path, quality=95)
        paths.append(path)

    pptx = OUT / "lebenslauf-boost-ai-praesentation.pptx"
    pdf = OUT / "lebenslauf-boost-ai-praesentation.pdf"
    save_pptx(paths, pptx)
    save_pdf(paths, pdf)
    print(f"Erstellt: {pptx}")
    print(f"Erstellt: {pdf}")
    print(f"Folien: {len(paths)}")


if __name__ == "__main__":
    main()
