"""Professionelles Sapphire-Nightfall Projektvideo (ca. 3–5 Minuten).

Voraussetzungen (macOS): ffmpeg, ffprobe, say (Stimme Anna), Pillow.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = ROOT / "docs" / "video"
ASSETS = VIDEO_DIR / "assets"
BUILD = VIDEO_DIR / "build"
WIDTH, HEIGHT = 1920, 1080
FPS = 30

# Sapphire Nightfall
INK = "#262b40"
ACCENT = "#0474c4"
ACCENT2 = "#06457f"
SOFT = "#a8c4ec"
BRIGHT = "#5379ae"
PAPER = "#eef3fa"
MUTED = "#9eb6d4"
WHITE = "#f0f5fc"


@dataclass(frozen=True)
class Scene:
    key: str
    image: Path
    narration: str


NARRATIONS = {
    "title": (
        "Willkommen zur Projektvorstellung von Lebenslauf Boost AI. "
        "Die aktuelle Webanwendung im Sapphire Nightfall Design begleitet Bewerbende mit dem Maskottchen Boosti "
        "durch einen klaren, dreistufigen Workflow. "
        "Zwei Sprachmodelle, Retrieval Augmented Generation, ein ATS Keyword Check und sechs Export Designs "
        "sind in einer einzigen Anwendung vereint — ohne Anmeldung und strikt auf echten Lebenslauf Daten."
    ),
    "hero": (
        "So sieht die aktuelle Website aus: ein dunkler Hero Bereich mit klarer Botschaft, "
        "ein dreistufiger Stepper und darunter die Erklaerung in sechs einfachen Schritten. "
        "Die Oberflaeche ist auf Deutsch und Englisch verfuegbar. "
        "Im Zentrum steht: der Lebenslauf wird zugeschnitten auf die Stelle, ohne Fakten zu erfinden."
    ),
    "input": (
        "Schritt eins beginnt mit der Stellenanzeige und optionalen Wuenschen zu Ton, Fokus und Laenge. "
        "Danach wird der Lebenslauf als PDF, Word oder Textdatei hochgeladen. "
        "Fuer Claude und OpenAI gibt es direkte Links, falls noch kein API Key vorhanden ist. "
        "Ohne Key laeuft der Demo Modus. Die App extrahiert Text und optional ein Foto und baut den RAG Index auf."
    ),
    "loading": (
        "Beim Klick auf Generieren erscheint eine fuenfsekundige Ladesequenz. "
        "Fortschrittsring, Checkliste und Schreibanimation machen sichtbar, dass die KI die Stelle analysiert, "
        "passende Staerken waehlt und den Entwurf formuliert. "
        "Erst danach wechselt die App zur Bearbeitungsseite."
    ),
    "generation": (
        "Auf der Bearbeitungsseite koennen Claude und OpenAI direkt verglichen werden. "
        "Fuer jede Version zeigt die App ATS Score, Keyword Check sowie Modell und Prompt Technik. "
        "Professionelle Prompt Vorlagen mit Rollen Prompting, Few Shot und Chain of Thought steuern die Formulierung. "
        "Die KI darf nur Angaben verwenden, die im hochgeladenen Lebenslauf belegt sind."
    ),
    "refine": (
        "Der Entwurf laesst sich im Editor direkt anpassen. "
        "Zusaetzlich gibt es Schnellaktionen und freie Anweisungen, zum Beispiel kuerzer, technischer oder foermlicher. "
        "Jede Antwort wird ueber Conversation History als eigene Version gespeichert. "
        "So bleibt der Kontext erhalten, ohne den gesamten Prozess neu zu starten."
    ),
    "export": (
        "Im dritten Schritt waehlt man eines von sechs Designs: Azure, Executive, Nordic, Sapphire, Cobalt oder Slate. "
        "Die Live Vorschau aktualisiert sich sofort. Foto, Dateiname und Format PDF oder Word sind frei waehlbar. "
        "Der Download startet lokal. Der Export bleibt zustandslos und speichert keine zusaetzliche Datei in der Datenbank."
    ),
    "architecture": (
        "Technisch besteht das Projekt aus einem Vanilla JavaScript Frontend und einem FastAPI Backend. "
        "Pydantic validiert alle Requests. Eine Provider Schicht kapselt Anthropic Claude und OpenAI. "
        "Services uebernehmen Extraktion, RAG, Prompt Aufbau, ATS Analyse und den PDF sowie DOCX Export. "
        "API Keys folgen dem Bring Your Own Key Prinzip und bleiben nur im Browser."
    ),
    "database": (
        "Die Persistenz nutzt SQLite mit SQLAlchemy. "
        "Die Tabelle sessions verbindet cv documents, generations und messages. "
        "Damit bleiben Versionshistorie, ATS Ergebnisse, Keyword Listen und der Dialog fuer Verfeinerungen "
        "nachvollziehbar und konsistent."
    ),
    "outro": (
        "Lebenslauf Boost AI zeigt damit den vollstaendigen Weg auf der aktuellen Website: "
        "echte Daten hochladen, relevanten Kontext finden, zwei KI Entwuerfe vergleichen, "
        "gezielt nachbessern und in sechs Designs professionell exportieren. "
        "Vielen Dank fuer das Ansehen."
    ),
}

GERMAN_WORDS = {
    "fuer": "für", "Fuer": "Für", "ueber": "über", "uebertragen": "übertragen",
    "vollstaendig": "vollständig", "vollstaendige": "vollständige", "vollstaendigen": "vollständigen",
    "verfuegbar": "verfügbar", "Verfuegung": "Verfügung", "einfuegt": "einfügt", "eingefuegt": "eingefügt",
    "muessen": "müssen", "loest": "löst", "zusaetzlich": "zusätzlich", "Zusaetzlich": "Zusätzlich",
    "Anschliessend": "Anschließend", "Wuensche": "Wünsche", "Nutzerwuensche": "Nutzerwünsche",
    "Laenge": "Länge", "waehlt": "wählt", "ausgewaehlt": "ausgewählt", "gewaehlt": "gewählt",
    "naechsten": "nächsten", "naechste": "nächste", "Naechste": "Nächste", "moeglich": "möglich",
    "koennen": "können", "kuerzer": "kürzer", "unabhaengige": "unabhängige",
    "Gespraechsverlauf": "Gesprächsverlauf", "behaelt": "behält", "laedt": "lädt",
    "zusaetzliche": "zusätzliche", "Schluesselbegriffe": "Schlüsselbegriffe", "Auszuege": "Auszüge",
    "Loeschen": "Löschen", "loeschen": "löschen", "hoechstens": "höchstens", "enthaelt": "enthält",
    "erfuellt": "erfüllt", "waeren": "wären", "Entwuerfe": "Entwürfe", "Oberflaeche": "Oberfläche",
    "pruefbar": "prüfbar", "laeuft": "läuft", "fuenfsekundige": "fünfsekundige",
    "durchgaengigen": "durchgängigen", "Erklaerung": "Erklärung", "Schritt": "Schritt",
    "Uebergang": "Übergang", "laesst": "lässt", "foermlicher": "förmlicher",
}


def germanize(text: str) -> str:
    result = text
    for source, target in sorted(GERMAN_WORDS.items(), key=lambda item: -len(item[0])):
        result = re.sub(rf"\b{re.escape(source)}\b", target, result)
    return result


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def font(size: int, bold: bool = False, serif: bool = False) -> ImageFont.FreeTypeFont:
    if serif:
        path = Path("/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Georgia.ttf")
    else:
        path = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, selected: ImageFont.ImageFont, width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=selected) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def sapphire_bg() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), INK)
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(0x26 + (0x06 - 0x26) * t * 0.5)
        g = int(0x2b + (0x45 - 0x2b) * t * 0.5)
        b = int(0x40 + (0x7f - 0x40) * t * 0.55)
        draw.line((0, y, WIDTH, y), fill=(r, g, b))
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-300, -180, 700, 720), fill=(4, 116, 196, 45))
    od.ellipse((1200, 380, 2200, 1280), fill=(168, 196, 236, 38))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def title_card(path: Path, eyebrow: str, title: str, subtitle: str, footer: str) -> None:
    image = sapphire_bg()
    draw = ImageDraw.Draw(image)
    # badge
    bw = int(draw.textlength(eyebrow.upper(), font=font(18, True))) + 36
    draw.rounded_rectangle((WIDTH // 2 - bw // 2, 150, WIDTH // 2 + bw // 2, 196), radius=22, fill=ACCENT)
    draw.text((WIDTH // 2, 173), eyebrow.upper(), anchor="mm", font=font(18, True), fill="#fff")

    y = 280
    for line in wrap(draw, title, font(72, True, serif=True), 1500):
        draw.text((WIDTH // 2, y), line, anchor="ma", font=font(72, True, serif=True), fill=WHITE)
        y += 90
    y += 20
    for line in wrap(draw, subtitle, font(28), 1200):
        draw.text((WIDTH // 2, y), line, anchor="ma", font=font(28), fill=MUTED)
        y += 42
    draw.line((720, 860, 1200, 860), fill=SOFT, width=3)
    draw.text((WIDTH // 2, 920), footer, anchor="ma", font=font(22, True), fill=SOFT)
    image.save(path)


def architecture_card(path: Path) -> None:
    image = sapphire_bg()
    draw = ImageDraw.Draw(image)
    draw.text((100, 70), "Architektur", font=font(50, True, serif=True), fill=WHITE)
    draw.text((100, 140), "Wie die aktuelle Website technisch aufgebaut ist", font=font(24), fill=MUTED)
    boxes = [
        (90, 280, 450, 700, "Frontend", ["Sapphire Nightfall", "Boosti-Tour DE/EN", "5s Lade-Overlay", "BYOK + Key-Links"], ACCENT),
        (500, 280, 860, 700, "Backend", ["FastAPI", "Pydantic", "Orchestrierung", "Export-Service"], ACCENT2),
        (910, 230, 1330, 470, "KI & RAG", ["Claude + OpenAI", "Professionelle Prompts", "ATS-Analyse"], BRIGHT),
        (910, 510, 1330, 750, "Services", ["Datei-Extraktion", "RAG Index", "PDF / DOCX"], "#2c444c"),
        (1380, 320, 1830, 680, "SQLite", ["sessions", "cv_documents", "generations", "messages"], INK),
    ]
    for x1, y1, x2, y2, heading, lines, color in boxes:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=20, fill=(15, 28, 48), outline=SOFT, width=2)
        draw.rounded_rectangle((x1, y1, x2, y1 + 64), radius=20, fill=color)
        draw.rectangle((x1, y1 + 36, x2, y1 + 64), fill=color)
        draw.text(((x1 + x2) // 2, y1 + 32), heading, anchor="mm", font=font(24, True), fill="#fff")
        y = y1 + 100
        for line in lines:
            draw.ellipse((x1 + 28, y + 4, x1 + 40, y + 16), fill=SOFT)
            draw.text((x1 + 54, y), line, font=font(20), fill=WHITE)
            y += 48
    draw.text((100, 920), "Upload → RAG → Prompt → Provider → ATS → Refine → Export", font=font(24, True), fill=SOFT)
    image.save(path)


def database_card(path: Path) -> None:
    image = sapphire_bg()
    draw = ImageDraw.Draw(image)
    draw.text((100, 70), "Datenmodell", font=font(50, True, serif=True), fill=WHITE)
    draw.text((100, 140), "Vier Tabellen für Session, CV, Generierungen und Dialog", font=font(24), fill=MUTED)
    src = ROOT / "docs" / "schema.png"
    if src.exists():
        with Image.open(src).convert("RGB") as schema:
            schema.thumbnail((1700, 780), Image.Resampling.LANCZOS)
            x = (WIDTH - schema.width) // 2
            y = 220
            shadow = Image.new("RGBA", (schema.width + 30, schema.height + 30), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle((6, 8, schema.width + 6, schema.height + 10), radius=16, fill=(0, 0, 0, 70))
            shadow = shadow.filter(ImageFilter.GaussianBlur(12))
            image.paste(shadow, (x - 6, y - 4), shadow)
            image.paste(schema, (x, y))
    image.save(path)


def frame_screenshot(source: Path, destination: Path, title: str, subtitle: str = "") -> None:
    base = sapphire_bg()
    draw = ImageDraw.Draw(base)
    draw.text((90, 48), title, font=font(36, True, serif=True), fill=WHITE)
    if subtitle:
        draw.text((92, 100), subtitle, font=font(20), fill=MUTED)

    # browser chrome
    frame = (90, 150, 1830, 1000)
    draw.rounded_rectangle(frame, radius=18, fill="#121a2a", outline=SOFT, width=2)
    draw.rounded_rectangle((90, 150, 1830, 198), radius=18, fill="#1a2740")
    draw.rectangle((90, 180, 1830, 198), fill="#1a2740")
    for i, color in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        cx = 130 + i * 28
        draw.ellipse((cx, 166, cx + 14, 180), fill=color)
    draw.rounded_rectangle((240, 162, 900, 186), radius=8, fill="#0d1524")
    draw.text((250, 174), "localhost:8000", anchor="lm", font=font(14), fill=MUTED)

    with Image.open(source).convert("RGB") as shot:
        max_w, max_h = 1700, 760
        shot.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        x = (WIDTH - shot.width) // 2
        y = 220 + (760 - shot.height) // 2
        base.paste(shot, (x, y))
    base.save(destination)


def make_slides() -> None:
    title_card(
        ASSETS / "00-title.png",
        "Projektvideo",
        "Lebenslauf Boost AI",
        "Sapphire Nightfall · Boosti · RAG · Claude & OpenAI · 6 Designs",
        "FastAPI  ·  SQLite  ·  BYOK  ·  PDF & Word",
    )
    frame_screenshot(ASSETS / "01-hero.png", ASSETS / "01-hero-framed.png", "Die aktuelle Website", "Hero, Stepper und Boosti im Sapphire Nightfall Design")
    frame_screenshot(ASSETS / "02-input-upload.png", ASSETS / "02-input-framed.png", "Schritt 1 · Eingabe", "Stellenanzeige, CV-Upload und API-Key-Links")
    frame_screenshot(ASSETS / "02b-loading.png", ASSETS / "02b-loading-framed.png", "Ladesequenz", "Fünf Sekunden Fortschritt vor dem Seitenwechsel")
    frame_screenshot(ASSETS / "03-compare-output.png", ASSETS / "03-compare-framed.png", "Schritt 2 · Bearbeiten", "Modellvergleich, ATS-Score und Keyword-Check")
    frame_screenshot(ASSETS / "04-refine.png", ASSETS / "04-refine-framed.png", "Verfeinern", "Conversation History und iterative Verbesserung")
    frame_screenshot(ASSETS / "05-design-export.png", ASSETS / "05-design-framed.png", "Schritt 3 · Design & Download", "Sechs Designs, Live-Vorschau, PDF oder Word")
    architecture_card(ASSETS / "06-architecture.png")
    database_card(ASSETS / "07-database.png")
    title_card(
        ASSETS / "09-outro.png",
        "Fazit",
        "Vom Original-CV zum Export",
        "Echte Daten · kontrollierte KI · professionelles Ergebnis",
        "Lebenslauf Boost AI",
    )


def tts(scene: Scene, index: int) -> tuple[Path, float]:
    audio = BUILD / f"{index:02d}-{scene.key}.aiff"
    run(["say", "-v", "Anna", "-r", "148", "-o", str(audio), germanize(scene.narration)])
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(audio)],
        check=True, text=True, capture_output=True,
    )
    return audio, float(probe.stdout.strip())


def srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def subtitle_chunks(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    for sentence in sentences:
        if len(sentence) <= 105:
            chunks.append(sentence)
        else:
            chunks.extend(textwrap.wrap(sentence, width=92, break_long_words=False))
    return [c for c in chunks if c]


def write_subtitles(timed: list[tuple[Scene, float, float]]) -> Path:
    target = VIDEO_DIR / "lebenslauf-boost-ai-projektvideo.srt"
    entries, counter = [], 1
    for scene, start, duration in timed:
        chunks = subtitle_chunks(germanize(scene.narration))
        weights = [max(len(c), 20) for c in chunks]
        total = sum(weights)
        cursor = start + 0.25
        usable = max(duration - 0.6, 0.5)
        for chunk, weight in zip(chunks, weights):
            end = cursor + usable * weight / total
            entries.append(f"{counter}\n{srt_time(cursor)} --> {srt_time(end)}\n{chunk}\n")
            counter += 1
            cursor = end
    target.write_text("\n".join(entries), encoding="utf-8")
    return target


def render_scene(scene: Scene, audio: Path, duration: float, index: int) -> Path:
    output = BUILD / f"{index:02d}-{scene.key}.mp4"
    final_duration = duration + 0.7
    fade_out = max(final_duration - 0.5, 0)
    video_filter = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"zoompan=z='min(zoom+0.00005,1.02)':d=1:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out:.3f}:d=0.45"
    )
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(scene.image), "-i", str(audio),
        "-vf", video_filter,
        "-af", f"afade=t=in:st=0:d=0.2,afade=t=out:st={max(duration - 0.3, 0):.3f}:d=0.25",
        "-t", f"{final_duration:.3f}",
        "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(output),
    ])
    return output


def build_video() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    make_slides()
    scenes = [
        Scene("title", ASSETS / "00-title.png", NARRATIONS["title"]),
        Scene("hero", ASSETS / "01-hero-framed.png", NARRATIONS["hero"]),
        Scene("input", ASSETS / "02-input-framed.png", NARRATIONS["input"]),
        Scene("loading", ASSETS / "02b-loading-framed.png", NARRATIONS["loading"]),
        Scene("generation", ASSETS / "03-compare-framed.png", NARRATIONS["generation"]),
        Scene("refine", ASSETS / "04-refine-framed.png", NARRATIONS["refine"]),
        Scene("export", ASSETS / "05-design-framed.png", NARRATIONS["export"]),
        Scene("architecture", ASSETS / "06-architecture.png", NARRATIONS["architecture"]),
        Scene("database", ASSETS / "07-database.png", NARRATIONS["database"]),
        Scene("outro", ASSETS / "09-outro.png", NARRATIONS["outro"]),
    ]

    rendered, timed, elapsed = [], [], 0.0
    for index, scene in enumerate(scenes, 1):
        audio, audio_duration = tts(scene, index)
        scene_duration = audio_duration + 0.7
        timed.append((scene, elapsed, scene_duration))
        rendered.append(render_scene(scene, audio, audio_duration, index))
        elapsed += scene_duration

    concat_file = BUILD / "concat.txt"
    concat_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in rendered), encoding="utf-8")
    uncaptioned = BUILD / "project-video-uncaptioned.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", "-movflags", "+faststart", str(uncaptioned)])

    subtitles = write_subtitles(timed)
    final = VIDEO_DIR / "lebenslauf-boost-ai-projektvideo.mp4"
    # Burn-in optional; fallback to separate SRT if libass missing
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(uncaptioned), "-c", "copy", "-movflags", "+faststart", str(final)],
        cwd=ROOT, text=True,
    )
    if result.returncode != 0:
        shutil.copy2(uncaptioned, final)
    else:
        # Prefer clean copy; SRT shipped alongside
        pass

    speaker = VIDEO_DIR / "sprechertext.txt"
    speaker.write_text(
        "\n\n".join(f"{i}. {s.key.upper()}\n{germanize(s.narration)}" for i, s in enumerate(scenes, 1)),
        encoding="utf-8",
    )
    print(f"\nFertig: {final}\nUntertitel: {subtitles}\nLaufzeit: {elapsed:.1f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    build_video()
