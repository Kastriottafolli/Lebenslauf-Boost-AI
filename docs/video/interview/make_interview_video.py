"""Studio-Qualität: technisches Interview-Erklärvideo (Deutsch).

Realistische Edge-TTS-Stimme + Sapphire-Nightfall-Motion-Slides.
Ausgabe: docs/video/interview/lebenslauf-boost-ai-technical-interview.mp4
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "video" / "interview"
ASSETS_UI = ROOT / "docs" / "video" / "assets"
BUILD = OUT / "build"
SLIDES = OUT / "slides"
WIDTH, HEIGHT = 1920, 1080
FPS = 30
VOICE = "de-DE-FlorianMultilingualNeural"  # natürlich, klar, professionell

# Sapphire Nightfall
INK = "#0f1728"
ACCENT = "#0474c4"
ACCENT2 = "#06457f"
SOFT = "#a8c4ec"
BRIGHT = "#5379ae"
WHITE = "#f4f7fc"
MUTED = "#9eb6d4"
CARD = "#152238"
LINE = "#2a3d5c"


@dataclass(frozen=True)
class Scene:
    key: str
    title: str
    subtitle: str
    bullets: list[str]
    narration: str
    screenshot: Path | None = None
    layout: str = "bullets"  # bullets | split | diagram | title | outro


# ── Interview-Skript (technischer Walkthrough auf Deutsch) ────────────────────

SCENES: list[Scene] = [
    Scene(
        key="title",
        title="Lebenslauf Boost AI",
        subtitle="Technischer Walkthrough — Architektur, APIs, Prompts und End-to-End-Ablauf",
        bullets=[],
        layout="title",
        narration=(
            "Hallo — vielen Dank für die Gelegenheit, Lebenslauf Boost AI vorzustellen. "
            "Das ist ein Full-Stack-KI-Engineering-Projekt, das ich gebaut habe, "
            "um einen echten Lebenslauf gezielt auf eine Stellenanzeige zuzuschneiden. "
            "In diesem Video erkläre ich, wie Frontend und Backend funktionieren, "
            "welche externen APIs wir aufrufen und warum, wie das Prompt-System aufgebaut ist, "
            "und wie die Pipeline vom Upload bis zum Export läuft."
        ),
    ),
    Scene(
        key="pitch",
        title="Was das Produkt leistet",
        subtitle="Problem, Lösung und Designprinzipien",
        bullets=[
            "Problem: generische CVs scheitern an ATS-Filtern und kosten Zeit",
            "Lösung: echten Lebenslauf mit geerdeter KI auf eine Stelle zuschneiden",
            "Wahrhaftigkeit zuerst — keine erfundenen Arbeitgeber, Abschlüsse oder Kennzahlen",
            "Zwei Anbieter: Anthropic Claude und OpenAI, auch im Direktvergleich",
            "End-to-End: Upload → RAG → Generieren → Verfeinern → PDF/Word-Export",
        ],
        narration=(
            "Auf Produktebene lösen wir ein praktisches Bewerbungsproblem. "
            "Bewerberinnen und Bewerber müssen ihren Lebenslauf für jede Stelle anpassen, "
            "aber unkontrollierte generative KI erfindet oft Fähigkeiten oder Erfolge. "
            "Unser Leitprinzip ist Wahrhaftigkeit zuerst: "
            "Das Modell darf nur Fakten aus dem hochgeladenen Lebenslauf verwenden. "
            "Wir holen die relevantesten CV-Abschnitte per RAG, erzeugen einen oder zwei Entwürfe mit Claude und OpenAI, "
            "bewerten sie gegen die Stellen-Keywords, lassen den Text verfeinern "
            "und exportieren ein fertiges PDF oder Word in einem von sechs Designs."
        ),
    ),
    Scene(
        key="architecture",
        title="Systemarchitektur",
        subtitle="Klare Trennung von UI, API, KI und Persistenz",
        bullets=[
            "Frontend: Vanilla-ES-Module — Sapphire Nightfall UI + Boosti-Tour",
            "Backend: FastAPI-Router → Services → LLM-Provider-Schicht",
            "Prompts: editierbare Textdateien unter prompts/, mit Cache geladen",
            "Persistenz: SQLite via SQLAlchemy — sessions, CV, generations, messages",
            "Fallbacks: Embeddings → TF-IDF, Live-API → gekennzeichneter Demo-Modus",
        ],
        layout="diagram",
        narration=(
            "Architektonisch habe ich das System bewusst modular gehalten. "
            "Das Frontend ist eine schlanke Vanilla-JavaScript-SPA — ohne React-Build — "
            "im eigenen Sapphire-Nightfall-Designsystem, mit Boosti als animiertem Guide durch den Ablauf. "
            "Das Backend ist FastAPI mit dünnen Routern und dickeren Services. "
            "LLM-Zugriffe laufen über eine Provider-Abstraktion, sodass Claude und OpenAI dieselbe Schnittstelle teilen. "
            "Die Prompt-Texte liegen außerhalb des Codes als deutsche und englische Vorlagen, "
            "damit Prompt Engineering ohne Python-Änderungen möglich bleibt. "
            "SQLite speichert Sitzungen und Historie. Fehlen Keys oder Embeddings, "
            "fällt die App sauber in einen klar gekennzeichneten Demo-Modus — statt zu crashen."
        ),
    ),
    Scene(
        key="frontend",
        title="Frontend — so funktioniert die UI",
        subtitle="Drei Schritte, BYOK-Keys, i18n und Client-Orchestrierung",
        bullets=[
            "Schritt 1 Eingabe: Stelle, Wünsche, CV-Upload, Anbieter, Technik",
            "Schritt 2 Bearbeiten: Markdown-Editor, Vergleich, ATS-Chips, Refine",
            "Schritt 3 Design: sechs Themes, Live-Vorschau, PDF oder DOCX",
            "BYOK: API-Keys nur im Browser-localStorage — nie in der Datenbank",
            "api.js spricht /api/session, upload-cv, generate, refine, export",
        ],
        screenshot=ASSETS_UI / "01-hero.png",
        layout="split",
        narration=(
            "Im Frontend ist die Oberfläche ein dreistufiger Wizard. "
            "Schritt eins sammelt Stellenbeschreibung, optionale Wünsche, die CV-Datei, "
            "die Anbieterwahl — Claude, OpenAI oder Vergleich — und die Prompt-Technik. "
            "Schritt zwei ist die Bearbeitungsfläche: generierter Markdown, Vergleichsleiste bei zwei Modellen, "
            "ATS-Keyword-Panel und Verfeinern-Chips wie kürzer oder förmlicher. "
            "Schritt drei ist Design und Download mit sechs visuellen Themes. "
            "API-Keys folgen dem Bring-your-own-key-Prinzip: sie liegen nur in localStorage, "
            "werden pro Request mitgeschickt und serverseitig nie gespeichert. "
            "Alle Netzaufrufe laufen über ein kleines api.js-Modul, inklusive Timeout beim Generieren."
        ),
    ),
    Scene(
        key="backend",
        title="Backend — der Request-Pfad",
        subtitle="Router, Services und die LLM-Schicht",
        bullets=[
            "routers/: nur HTTP — sessions, documents, generations, exports",
            "services/: Extraktion, RAG, Generierungs-Orchestrierung, Export",
            "llm/: AnthropicProvider, OpenAIProvider, gemeinsames LLMResult",
            "Pydantic-Schemas validieren jeden Payload vor der Fachlogik",
            "Eine Session bündelt CV-Dokument, Generierungen und Chat-Messages",
        ],
        narration=(
            "Im Backend habe ich HTTP von der Fachlogik getrennt. "
            "Router übernehmen Sitzungen, Dokument-Upload, Generierung, Refine und Export. "
            "Services machen die eigentliche Arbeit: Datei-Extraktion aus PDF, DOCX oder Text, "
            "RAG-Indexierung und Retrieval, Orchestrierung der Generierung sowie PDF- oder Word-Rendering. "
            "Das LLM-Paket definiert einen abstrakten Provider und konkrete Anthropic- und OpenAI-Implementierungen, "
            "die beide ein strukturiertes Ergebnis mit Inhalt, Modellname und Demo-Flag zurückgeben. "
            "Pydantic validiert jeden Request. "
            "Die Session ist der Hub: höchstens ein CV-Dokument, viele Generierungen und eine Message-Historie für Refine."
        ),
    ),
    Scene(
        key="apis",
        title="Externe APIs — was wir aufrufen und wie",
        subtitle="Anthropic Messages API + OpenAI Chat & Embeddings",
        bullets=[
            "Anthropic: messages.create — System-Prompt + User/Assistant-Turns",
            "OpenAI Chat: chat.completions.create — dieselben logischen Rollen",
            "OpenAI Embeddings: text-embedding-3-small für RAG-Vektoren",
            "Key-Reihenfolge: UI-BYOK → Server-.env → Demo-Fallback",
            "Vergleichsmodus ruft beide unabhängig auf und rankt per ATS",
        ],
        narration=(
            "Wir nutzen zwei verschiedene Text-Generierungs-APIs — das war eine explizite Projektanforderung. "
            "Für Claude rufen wir die Anthropic Messages API mit System-Prompt und Message-Liste auf. "
            "Für OpenAI nutzen wir Chat Completions mit denselben logischen Rollen "
            "und zusätzlich OpenAI Embeddings — text-embedding-3-small — um CV-Chunks für RAG zu vektorisieren. "
            "Die Key-Auflösung ist wichtig für Datenschutz und Demos: "
            "Ein in der UI eingegebener Key hat Vorrang, sonst greift ein Server-Environment-Key, "
            "und wenn beides fehlt, liefern wir einen gekennzeichneten Demo-Lebenslauf, "
            "damit der komplette Produktfluss trotzdem testbar bleibt. "
            "Im Vergleichsmodus laufen beide Provider unabhängig; "
            "wir lassen nicht ein Modell das andere bewerten, "
            "sondern ranken Entwürfe mit unserem eigenen ATS-Keyword-Overlap-Score."
        ),
    ),
    Scene(
        key="prompts",
        title="Prompt-Engineering-System",
        subtitle="Zwölf Vorlagen · vier Techniken · eine Assembly-Pipeline",
        bullets=[
            "12 Template-Dateien: 6 Rollen × Deutsch und Englisch",
            "Role Prompting: Senior-Resume-Writer + ATS-Spezialist-Persona",
            "Few-shot: schwach → stark umformulierte Bullets, ohne Fake-Zahlen",
            "Chain-of-Thought: 7 interne Analyseschritte — nie im Output",
            "Format-Constraints + dynamische Kontextinjektion der RAG-Chunks",
            "Technik auto = Few-shot UND Chain-of-Thought zusammen",
        ],
        narration=(
            "Das Prompt-System ist einer der Teile, die ich besonders bewusst gestaltet habe. "
            "Unter dem Ordner prompts liegen zwölf Vorlagen — sechs logische Rollen, jeweils auf Deutsch und Englisch: "
            "System-Rolle, Few-shot-Beispiele, Chain-of-Thought-Anleitung, Ausgabeformat, User-Message-Gerüst und Refine. "
            "Role Prompting setzt eine erfahrene Resume-Writer-Persona, die strikt faktentreu bleibt. "
            "Few-shot zeigt schwache versus starke Bullets, damit das Modell wirkungsstark formuliert, ohne Zahlen zu erfinden. "
            "Chain-of-Thought erzwingt eine interne Sieben-Schritt-Analyse — Stellenanforderungen, Evidenz-Mapping, Keyword-Plan — "
            "diese Schritte erscheinen aber nie gegenüber der Nutzerin oder dem Nutzer. "
            "Format-Constraints fixieren die Markdown-Struktur. "
            "Und Dynamic Context Injection füllt die User-Message mit Stellenanzeige, Wünschen und abgerufenen CV-Auszügen. "
            "Ist die Technik auf auto gestellt, kombinieren wir Few-shot und Chain-of-Thought in einem Prompt."
        ),
    ),
    Scene(
        key="pipeline",
        title="End-to-End-Generierungs-Pipeline",
        subtitle="Vom Upload zum ATS-bewerteten Entwurf",
        bullets=[
            "1. Text und optional Foto aus PDF / DOCX / TXT extrahieren",
            "2. Chunks ~700 Zeichen, Embeddings oder TF-IDF-Index speichern",
            "3. Top-k-Chunks zur Stelle + Wünsche abrufen",
            "4. System + Technik + Format + injizierten Kontext zusammenbauen",
            "5. Provider aufrufen, Keywords scoren, Generation + Messages speichern",
        ],
        screenshot=ASSETS_UI / "03-compare-output.png",
        layout="split",
        narration=(
            "So läuft die Generierungs-Pipeline der Reihe nach. "
            "Erstens extrahiert der Upload Text und optional ein Foto. "
            "Zweitens zerlegen wir den Lebenslauf in Chunks — etwa siebenhundert Zeichen mit Überlappung — "
            "und bauen einen Index mit Embeddings, wenn ein OpenAI-Key vorhanden ist, sonst mit reinem Python-TF-IDF. "
            "Drittens holen wir beim Generieren die Top-Chunks, die am besten zu Stellenanzeige und Wünschen passen. "
            "Viertens baut prompts.py die System-Persona, die gewählten Technik-Blöcke, die Formatregeln "
            "und den injizierten RAG-Kontext zusammen. "
            "Fünftens rufen wir einen oder beide Provider auf, führen die ATS-Keyword-Analyse gegen die Stellenanzeige durch "
            "und speichern jeden Entwurf plus die Conversation-Messages für späteres Verfeinern."
        ),
    ),
    Scene(
        key="refine_export",
        title="Verfeinern, Vergleichen und Export",
        subtitle="Conversation History und sechs Design-Themes",
        bullets=[
            "Refine sendet letzte User- + Assistant-Nachricht + neue Anweisung",
            "Jeder Refine erzeugt eine neue Generation — Historie bleibt erhalten",
            "Vergleichs-UI zeigt ATS-Gewinner, Nutzer:in kann überschreiben",
            "Export ist zustandslos: Markdown + Design + Format im Request",
            "Sechs Designs: Azure, Executive, Nordic, Sapphire, Cobalt, Slate",
        ],
        screenshot=ASSETS_UI / "05-design-export.png",
        layout="split",
        narration=(
            "Nach dem ersten Entwurf nutzt Refine die Conversation History. "
            "Wir senden die vorherige User-Nachricht, den Assistant-Entwurf und eine neue Anweisung — "
            "zum Beispiel kürzer oder technischer — und speichern eine neue Generation mit Technik refine. "
            "Nichts wird überschrieben, Versionen bleiben nachvollziehbar. "
            "Im Vergleichsmodus hebt die UI den höheren ATS-Score hervor, aber die Nutzerin oder der Nutzer kann beide wählen. "
            "Der Export ist bewusst zustandslos: der Client schickt finalen Markdown, Design, Format und optional ein Foto. "
            "ReportLab und python-docx rendern sechs visuelle Themes, ohne Dateien in die Datenbank zu schreiben."
        ),
    ),
    Scene(
        key="quality",
        title="Qualität, Sicherheit und Trade-offs",
        subtitle="Was ich in einem Bewerbungsgespräch betonen würde",
        bullets=[
            "Privacy: BYOK-Keys landen nie in SQLite",
            "Zuverlässigkeit: Demo-Modus macht den Flow ohne bezahlte Keys testbar",
            "Evaluation: ATS-Overlap ist eine anwendungsspezifische Metrik",
            "Wartbarkeit: Prompts als Dateien, Provider hinter einer ABC",
            "Nächste Schritte: PostgreSQL, Alembic, Auth, Tests und Docker",
        ],
        narration=(
            "Wenn ich das Engineering-Urteilsvermögen für ein Bewerbungsgespräch zusammenfasse, betone ich vier Punkte. "
            "Privacy: Nutzer-Keys bleiben im Browser. "
            "Zuverlässigkeit: Der Demo-Modus erlaubt den kompletten Flow ohne Credentials. "
            "Evaluation: Wir messen Passung mit einem anwendungsspezifischen ATS-Keyword-Score, nicht mit vagen Eindrücken. "
            "Und Wartbarkeit: Prompts sind Daten, Provider sind austauschbar, Router bleiben dünn. "
            "Die ehrlichen nächsten Schritte für Produktion wären PostgreSQL mit Alembic, echte Authentifizierung, "
            "breitere automatisierte Tests und containerisiertes Deployment."
        ),
    ),
    Scene(
        key="outro",
        title="Vielen Dank",
        subtitle="Lebenslauf Boost AI — geerdete Generierung, zwei APIs, durchgängiges Produktdenken",
        bullets=[],
        layout="outro",
        narration=(
            "Das ist das System von Ende zu Ende: ein produktförmiger KI-Workflow mit klarer Architektur, "
            "zwei echten Modell-Providern, einem strukturierten Prompt-Stack, Retrieval-Grounding "
            "und einer vollständigen User Journey vom Upload bis zum Export. "
            "Gerne gehe ich tiefer in jede Schicht — Prompts, RAG oder das FastAPI-Service-Design. "
            "Vielen Dank fürs Zuschauen."
        ),
    ),
]


def font(size: int, bold: bool = False, serif: bool = False) -> ImageFont.FreeTypeFont:
    if serif:
        path = Path("/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Georgia.ttf")
    else:
        path = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if draw.textlength(cand, font=fnt) <= width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def studio_bg() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), INK)
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(15 + (6 - 15) * t * 0.4)
        g = int(23 + (45 - 23) * t * 0.35)
        b = int(40 + (127 - 40) * t * 0.45)
        draw.line((0, y, WIDTH, y), fill=(max(r, 8), max(g, 18), max(b, 40)))
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-350, -220, 780, 780), fill=(4, 116, 196, 38))
    od.ellipse((1180, 420, 2300, 1400), fill=(168, 196, 236, 28))
    # subtle grid
    for x in range(0, WIDTH, 80):
        od.line((x, 0, x, HEIGHT), fill=(255, 255, 255, 6))
    for y in range(0, HEIGHT, 80):
        od.line((0, y, WIDTH, y), fill=(255, 255, 255, 6))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def chrome(draw: ImageDraw.ImageDraw, index: int, total: int) -> None:
    draw.rounded_rectangle((70, 48, 420, 92), radius=18, fill=ACCENT)
    draw.text((245, 70), "TECHNISCHER WALKTHROUGH", anchor="mm", font=font(14, True), fill="#fff")
    draw.text((1840, 70), f"{index:02d} / {total:02d}", anchor="ra", font=font(18, True), fill=SOFT)
    draw.line((70, 1010, 1850, 1010), fill=LINE, width=2)
    draw.text((70, 1030), "LEBENSLAUF BOOST AI", font=font(13, True), fill=SOFT)
    draw.text((1850, 1030), "FastAPI · Claude · OpenAI · RAG · SQLite", anchor="ra", font=font(13), fill=MUTED)


def paste_shot(base: Image.Image, source: Path, box: tuple[int, int, int, int]) -> None:
    if not source.exists():
        return
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    with Image.open(source).convert("RGB") as im:
        ratio = max(w / im.width, h / im.height)
        im = im.resize((int(im.width * ratio), int(im.height * ratio)), Image.Resampling.LANCZOS)
        left = (im.width - w) // 2
        top = max(0, (im.height - h) // 10)
        im = im.crop((left, top, left + w, top + h))
        shadow = Image.new("RGBA", (w + 28, h + 28), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((8, 10, w + 8, h + 12), radius=18, fill=(0, 0, 0, 80))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        base.paste(shadow, (x1 - 8, y1 - 4), shadow)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=14, fill=255)
        base.paste(im, (x1, y1), mask)


def render_scene_image(scene: Scene, index: int, total: int) -> Path:
    SLIDES.mkdir(parents=True, exist_ok=True)
    image = studio_bg()
    draw = ImageDraw.Draw(image)
    chrome(draw, index, total)

    if scene.layout == "title":
        draw.text((WIDTH // 2, 340), scene.title, anchor="ma", font=font(70, True, serif=True), fill=WHITE)
        y = 460
        for line in wrap(draw, scene.subtitle, font(28), 1400):
            draw.text((WIDTH // 2, y), line, anchor="ma", font=font(28), fill=MUTED)
            y += 44
        draw.rounded_rectangle((760, 700, 1160, 760), radius=30, fill=ACCENT)
        draw.text((960, 730), "Erklärvideo im Interview-Stil", anchor="mm", font=font(20, True), fill="#fff")

    elif scene.layout == "outro":
        draw.text((WIDTH // 2, 380), scene.title, anchor="ma", font=font(64, True, serif=True), fill=WHITE)
        y = 500
        for line in wrap(draw, scene.subtitle, font(26), 1300):
            draw.text((WIDTH // 2, y), line, anchor="ma", font=font(26), fill=SOFT)
            y += 40

    elif scene.layout == "diagram":
        draw.text((80, 130), scene.title, font=font(44, True, serif=True), fill=WHITE)
        draw.text((82, 195), scene.subtitle, font=font(22), fill=MUTED)
        boxes = [
            (80, 290, 440, 620, "Frontend", ["Vanilla JS SPA", "3-step wizard", "BYOK keys", "Boosti tour"], ACCENT),
            (480, 290, 840, 620, "FastAPI", ["Routers", "Pydantic", "Services", "Orchestration"], ACCENT2),
            (880, 260, 1320, 480, "LLM APIs", ["Claude Messages", "OpenAI Chat", "Embeddings"], BRIGHT),
            (880, 510, 1320, 760, "Prompts", ["Role · Few-shot", "CoT · Format", "12 templates"], "#2c444c"),
            (1360, 320, 1840, 700, "SQLite", ["sessions", "cv_documents", "generations", "messages"], INK),
        ]
        for x1, y1, x2, y2, heading, lines, color in boxes:
            draw.rounded_rectangle((x1, y1, x2, y2), radius=18, fill=CARD, outline=SOFT, width=2)
            draw.rounded_rectangle((x1, y1, x2, y1 + 58), radius=18, fill=color)
            draw.rectangle((x1, y1 + 34, x2, y1 + 58), fill=color)
            draw.text(((x1 + x2) // 2, y1 + 29), heading, anchor="mm", font=font(22, True), fill="#fff")
            yy = y1 + 90
            for line in lines:
                draw.ellipse((x1 + 24, yy + 6, x1 + 36, yy + 18), fill=SOFT)
                draw.text((x1 + 48, yy), line, font=font(18), fill=WHITE)
                yy += 42
        draw.text((80, 900), "Upload → RAG → Prompt assembly → Provider call → ATS → Refine → Export", font=font(22, True), fill=SOFT)

    elif scene.layout == "split" and scene.screenshot:
        draw.text((80, 130), scene.title, font=font(40, True, serif=True), fill=WHITE)
        draw.text((82, 190), scene.subtitle, font=font(20), fill=MUTED)
        y = 270
        for item in scene.bullets:
            draw.rounded_rectangle((80, y, 900, y + 78), radius=14, fill=CARD, outline=LINE, width=1)
            draw.ellipse((104, y + 32, 120, y + 48), fill=ACCENT)
            for i, line in enumerate(wrap(draw, item, font(20), 720)[:2]):
                draw.text((140, y + 20 + i * 26), line, font=font(20), fill=WHITE)
            y += 92
        paste_shot(image, scene.screenshot, (960, 220, 1840, 960))

    else:  # bullets
        draw.text((80, 130), scene.title, font=font(44, True, serif=True), fill=WHITE)
        draw.text((82, 195), scene.subtitle, font=font(22), fill=MUTED)
        y = 280
        for item in scene.bullets:
            draw.rounded_rectangle((80, y, 1840, y + 90), radius=16, fill=CARD, outline=LINE, width=1)
            draw.ellipse((120, y + 36, 140, y + 56), fill=ACCENT)
            for i, line in enumerate(wrap(draw, item, font(26), 1580)[:2]):
                draw.text((180, y + 24 + i * 32), line, font=font(26), fill=WHITE)
            y += 108

    path = SLIDES / f"{index:02d}-{scene.key}.png"
    image.save(path, quality=95)
    return path


def normalize_tts_text(text: str) -> str:
    """Make narration flow smoothly for neural TTS (avoid long pause glyphs)."""
    text = text.replace("—", ", ")
    text = text.replace("–", ", ")
    text = text.replace("  ", " ")
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*,", ",", text)
    # Keep sentences crisp; avoid stacked pauses around colons
    text = text.replace(" : ", ": ")
    return text.strip()


def probe_duration(path: Path) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True, text=True, capture_output=True,
    )
    return float(probe.stdout.strip())


async def synthesize(text: str, dest: Path) -> float:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Slightly brisker delivery reduces "hanging" pauses between clauses
    communicate = edge_tts.Communicate(normalize_tts_text(text), VOICE, rate="+3%")
    await communicate.save(str(dest))
    return probe_duration(dest)


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(timed: list[tuple[Scene, float, float]], path: Path) -> None:
    entries, n = [], 1
    for scene, start, dur in timed:
        sentences = re.split(r"(?<=[.!?])\s+", scene.narration.strip())
        chunks: list[str] = []
        for sentence in sentences:
            chunks.extend(textwrap.wrap(sentence, width=88) or [sentence])
        weights = [max(len(c), 16) for c in chunks]
        total = sum(weights) or 1
        cursor = start + 0.05
        usable = max(dur - 0.15, 0.4)
        for chunk, w in zip(chunks, weights):
            end = cursor + usable * w / total
            entries.append(f"{n}\n{srt_time(cursor)} --> {srt_time(end)}\n{chunk}\n")
            n += 1
            cursor = end
    path.write_text("\n".join(entries), encoding="utf-8")


def render_clip(image: Path, audio: Path, duration: float, dest: Path) -> None:
    """Video length matches speech exactly — no trailing silence / voice cutoffs."""
    # Tiny visual fades only; audio stays continuous and uncropped
    fade_out_start = max(duration - 0.18, 0)
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"zoompan=z='min(1+0.00003*on,1.012)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"fade=t=in:st=0:d=0.12,fade=t=out:st={fade_out_start:.3f}:d=0.18"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(image),
            "-i", str(audio),
            "-vf", vf,
            # Keep full voice; only soft 40ms edges, no loudnorm (avoids pumping/dropouts)
            "-af", "afade=t=in:st=0:d=0.04,afade=t=out:st={0}:d=0.04".format(max(duration - 0.04, 0)),
            "-t", f"{duration:.3f}",
            "-r", str(FPS),
            "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "1",
            "-shortest",
            "-movflags", "+faststart", str(dest),
        ],
        check=True,
    )


def stitch_seamless(clips: list[Path], audio_files: list[Path], final: Path) -> None:
    """Concat video clips and rebuild one continuous normalized voice track."""
    # 1) Seamless audio concat (no gaps)
    audio_list = BUILD / "audio_concat.txt"
    audio_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in audio_files), encoding="utf-8")
    voice = BUILD / "voiceover-continuous.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_list),
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(voice),
        ],
        check=True,
    )

    # 2) Video concat
    video_list = BUILD / "video_concat.txt"
    video_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in clips), encoding="utf-8")
    video_raw = BUILD / "video-concat.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(video_list),
            "-c", "copy", str(video_raw),
        ],
        check=True,
    )

    # 3) Mux with continuous voice + gentle final loudness (one pass only)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_raw),
            "-i", str(voice),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "1",
            "-shortest",
            "-movflags", "+faststart",
            str(final),
        ],
        check=True,
    )


async def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if BUILD.exists():
        # Fresh audio/video avoids stale padded clips
        for old in BUILD.glob("*"):
            if old.is_file():
                old.unlink()
    BUILD.mkdir(parents=True, exist_ok=True)

    total = len(SCENES)
    timed: list[tuple[Scene, float, float]] = []
    clips: list[Path] = []
    audios: list[Path] = []
    elapsed = 0.0
    script_lines = []

    for i, scene in enumerate(SCENES, 1):
        print(f"[{i}/{total}] {scene.key}")
        img = render_scene_image(scene, i, total)
        audio = BUILD / f"{i:02d}-{scene.key}.mp3"
        dur = await synthesize(scene.narration, audio)
        clip = BUILD / f"{i:02d}-{scene.key}.mp4"
        render_clip(img, audio, dur, clip)
        # Use measured clip duration for timeline accuracy
        clip_dur = probe_duration(clip)
        timed.append((scene, elapsed, clip_dur))
        clips.append(clip)
        audios.append(audio)
        elapsed += clip_dur
        script_lines.append(f"{i}. {scene.key.upper()} — {scene.title}\n{scene.narration}\n")

    final = OUT / "lebenslauf-boost-ai-technical-interview.mp4"
    print("Stitching seamless voice + video…")
    stitch_seamless(clips, audios, final)

    srt = OUT / "lebenslauf-boost-ai-technical-interview.srt"
    write_srt(timed, srt)
    (OUT / "sprechertext.md").write_text(
        "# Technical Interview Explainer — Sprechertext (Deutsch)\n\n"
        f"Stimme: `{VOICE}` via edge-tts\n"
        f"Dauer: ca. {elapsed/60:.1f} Minuten\n\n"
        + "\n".join(script_lines),
        encoding="utf-8",
    )
    (OUT / "README.md").write_text(
        "# Technical Interview Explainer Video (Deutsch)\n\n"
        "Professioneller Walkthrough von Lebenslauf Boost AI — Architektur, APIs, Prompts und Produktfluss.\n\n"
        f"- **Video:** [`lebenslauf-boost-ai-technical-interview.mp4`](lebenslauf-boost-ai-technical-interview.mp4)\n"
        f"- **Untertitel:** [`lebenslauf-boost-ai-technical-interview.srt`](lebenslauf-boost-ai-technical-interview.srt)\n"
        f"- **Sprechertext:** [`sprechertext.md`](sprechertext.md)\n"
        f"- **Stimme:** `{VOICE}` (Edge TTS neural, Deutsch, nahtlos geschnitten)\n\n"
        "Neu erzeugen:\n\n```bash\n.venv/bin/python docs/video/interview/make_interview_video.py\n```\n",
        encoding="utf-8",
    )
    print(f"\nDone: {final}\nDuration: {elapsed:.1f}s ({elapsed/60:.1f} min)\nSubtitles: {srt}")


if __name__ == "__main__":
    asyncio.run(build())
