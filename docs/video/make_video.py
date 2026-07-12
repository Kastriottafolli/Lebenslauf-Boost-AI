"""Erzeugt das deutsche 3-5-minuetige Projektvideo.

Voraussetzungen (macOS):
- ffmpeg / ffprobe
- say
- Pillow (aus den Projekt-Requirements)

Ausgabe:
- docs/video/lebenslauf-boost-ai-projektvideo.mp4
- docs/video/lebenslauf-boost-ai-projektvideo.srt
- docs/video/sprechertext.txt
"""

from __future__ import annotations

import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = ROOT / "docs" / "video"
ASSETS = VIDEO_DIR / "assets"
BUILD = VIDEO_DIR / "build"
WIDTH, HEIGHT = 1920, 1080
FPS = 30


@dataclass(frozen=True)
class Scene:
    key: str
    image: Path
    narration: str


NARRATIONS = {
    "title": (
        "Hallo und willkommen zur Vorstellung von Lebenslauf Boost AI. "
        "Das Projekt optimiert einen vorhandenen Lebenslauf gezielt fuer eine Stellenanzeige. "
        "Dabei verbindet es zwei Sprachmodelle, Retrieval Augmented Generation, "
        "einen ATS Keyword Check und den Export als PDF oder Word in einer einzigen Anwendung."
    ),
    "problem": (
        "Die Ausgangssituation ist einfach: Bewerberinnen und Bewerber muessen ihren Lebenslauf "
        "fuer jede Stelle neu anpassen. Das kostet Zeit, und generative KI kann dabei Fakten "
        "erfinden. Lebenslauf Boost AI loest beide Probleme. Die Anwendung verwendet nur Inhalte "
        "aus dem hochgeladenen Lebenslauf, waehlt die fuer die Stelle relevanten Abschnitte aus "
        "und erstellt daraus einen nachvollziehbaren Entwurf. Die gesamte Oberflaeche ist auf "
        "Deutsch und Englisch verfuegbar und funktioniert ohne Anmeldung."
    ),
    "input": (
        "Im ersten Schritt wird die vollstaendige Stellenanzeige eingefuegt. Zusaetzlich lassen "
        "sich Wuensche zu Ton, Schwerpunkt und Laenge festlegen. Danach wird der Lebenslauf als "
        "PDF, Word Dokument oder Textdatei hochgeladen. Die App extrahiert den Text und kann sogar "
        "ein Bewerbungsfoto erkennen. Anschliessend zerlegt das RAG Modul den Inhalt in Abschnitte "
        "und erstellt einen Suchindex. Ohne OpenAI Key wird automatisch ein lokaler TF IDF "
        "Fallback verwendet. So bleibt die Demo vollstaendig nutzbar."
    ),
    "generation": (
        "Fuer die Generierung kann Claude, OpenAI oder der direkte Vergleich gewaehlt werden. "
        "Die Prompt Pipeline kombiniert Rollen Prompting, Few Shot Beispiele und eine strukturierte "
        "Analyse. Stellenanzeige, Nutzerwuensche und passende RAG Auszuege werden dynamisch in den "
        "Prompt eingesetzt. Im Vergleichsmodus entstehen zwei unabhaengige Versionen. Danach "
        "berechnet die App fuer beide einen ATS Score. Hier zeigt die Demo eine vollstaendige "
        "Abdeckung der erkannten Schluesselbegriffe. Gleichzeitig bleiben Anbieter, Modell, "
        "Prompt Technik und Demo Status transparent sichtbar."
    ),
    "refine": (
        "Der generierte Inhalt kann direkt bearbeitet werden. Noch wichtiger ist die iterative "
        "Verbesserung. Eine Anweisung wie kuerzer, technischer oder formeller wird zusammen mit "
        "dem bisherigen Gespraechsverlauf an das Modell gesendet. Jede neue Antwort wird als "
        "eigene Version gespeichert. Dadurch geht der vorherige Stand nicht verloren und das "
        "Modell behaelt den Kontext, ohne den gesamten Prozess neu zu starten."
    ),
    "export": (
        "Im letzten Anwendungsschritt wird ein Design ausgewaehlt. Zur Verfuegung stehen Modern, "
        "Classic und Minimal. Die Vorschau zeigt sofort, wie der Lebenslauf aufgebaut sein wird. "
        "Auch ein automatisch erkanntes Foto kann ersetzt oder entfernt werden. Danach waehlt "
        "die Person PDF oder Word, legt den Dateinamen fest und laedt das fertige Dokument herunter. "
        "Der Export ist zustandslos und speichert keine zusaetzliche Datei in der Datenbank."
    ),
    "architecture": (
        "Technisch besteht das Projekt aus einem schlanken Vanilla JavaScript Frontend und einem "
        "FastAPI Backend. Pydantic validiert alle Requests. Eine eigene Provider Schicht kapselt "
        "Anthropic Claude und OpenAI, sodass beide ueber dieselbe Schnittstelle angesprochen werden. "
        "Die Fachlogik ist getrennt in Datei Extraktion, RAG und Keyword Analyse, Prompt Aufbau "
        "sowie PDF und DOCX Export. SQLAlchemy verbindet die Anwendung mit SQLite. API Keys folgen "
        "dem Bring Your Own Key Prinzip: Sie bleiben im Browser, werden nur fuer den Request "
        "uebertragen und niemals serverseitig gespeichert."
    ),
    "database": (
        "Die Datenbank ist um die Tabelle sessions aufgebaut. Eine Sitzung besitzt hoechstens "
        "ein CV Dokument und beliebig viele Generierungen sowie Nachrichten. CV documents speichert "
        "extrahierten Text, RAG Index und optional das Foto. Generations bildet die komplette "
        "Versionshistorie inklusive Anbieter, Modell, Prompt Technik, ATS Score und Keyword Listen. "
        "Messages enthaelt den Dialog fuer die iterative Verbesserung. Foreign Keys, Indizes, "
        "Check Constraints und kaskadierendes Loeschen sichern die Datenintegritaet."
    ),
    "quality": (
        "Damit erfuellt das Projekt die zentralen KI Engineering Anforderungen: zwei Text APIs, "
        "mehrere Prompt Techniken, dynamische Kontextinjektion, RAG, Conversation History, "
        "eine anwendungsspezifische Vergleichsanalyse und persistente Datenhaltung. Der Demo Modus "
        "macht alle Schritte ohne kostenpflichtigen API Aufruf pruefbar. Fuer einen produktiven "
        "Mehrbenutzerbetrieb waeren PostgreSQL, Alembic Migrationen, Authentifizierung und "
        "Objektspeicher die naechsten sinnvollen Ausbaustufen."
    ),
    "outro": (
        "Lebenslauf Boost AI zeigt damit einen vollstaendigen End to End Workflow: echte Daten "
        "hochladen, relevanten Kontext finden, zwei KI Entwuerfe vergleichen, gezielt nachbessern "
        "und ein professionelles Dokument exportieren. Vielen Dank fuer das Ansehen."
    ),
}

GERMAN_WORDS = {
    "fuer": "für",
    "Fuer": "Für",
    "ueber": "über",
    "uebertragen": "übertragen",
    "ueberschrieben": "überschrieben",
    "vollstaendig": "vollständig",
    "vollstaendige": "vollständige",
    "vollstaendigen": "vollständigen",
    "verfuegbar": "verfügbar",
    "Verfuegung": "Verfügung",
    "einfuegt": "einfügt",
    "eingefuegt": "eingefügt",
    "muessen": "müssen",
    "loest": "löst",
    "zusaetzlich": "zusätzlich",
    "Zusaetzlich": "Zusätzlich",
    "Anschliessend": "Anschließend",
    "Wuensche": "Wünsche",
    "Nutzerwuensche": "Nutzerwünsche",
    "Laenge": "Länge",
    "waehlt": "wählt",
    "ausgewaehlt": "ausgewählt",
    "gewaehlt": "gewählt",
    "haelt": "hält",
    "naechsten": "nächsten",
    "naechste": "nächste",
    "naechsten": "nächsten",
    "moeglich": "möglich",
    "koennen": "können",
    "kuerzer": "kürzer",
    "unabhaengige": "unabhängige",
    "Gespraechsverlauf": "Gesprächsverlauf",
    "behaelt": "behält",
    "laedt": "lädt",
    "zusaetzliche": "zusätzliche",
    "fuehrende": "führende",
    "Schluesselbegriffe": "Schlüsselbegriffe",
    "Schluessel": "Schlüssel",
    "Auszuege": "Auszüge",
    "zurueck": "zurück",
    "Loeschen": "Löschen",
    "loeschen": "löschen",
    "geloescht": "gelöscht",
    "hoechstens": "höchstens",
    "beliebig": "beliebig",
    "gehoeren": "gehören",
    "enthaelt": "enthält",
    "erfuellt": "erfüllt",
    "waeren": "wären",
    "Entwuerfe": "Entwürfe",
    "Oberflaeche": "Oberfläche",
    "pruefbar": "prüfbar",
    "Qualitaet": "Qualität",
    "Datenintegritaet": "Datenintegrität",
}


def germanize(text: str) -> str:
    """Wandelt die ASCII-Schreibweise in saubere deutsche Anzeige/Sprache um."""
    result = text
    for source, target in sorted(GERMAN_WORDS.items(), key=lambda item: -len(item[0])):
        result = re.sub(rf"\b{re.escape(source)}\b", target, result)
    return result


def run(command: list[str], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(command))
    return subprocess.run(command, cwd=cwd, check=check, text=True, capture_output=False)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Helvetica.ttc"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, selected_font: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
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


def background() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#0d0c12")
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = (
            int(13 + 10 * ratio),
            int(12 + 18 * ratio),
            int(18 + 22 * ratio),
        )
        draw.line((0, y, WIDTH, y), fill=color)
    draw.ellipse((-300, 80, 700, 1080), fill="#241b12")
    draw.ellipse((1250, -250, 2200, 700), fill="#1d1730")
    return image


def title_slide(path: Path, eyebrow: str, title: str, subtitle: str, footer: str) -> None:
    image = background()
    draw = ImageDraw.Draw(image)
    gold = "#e8b866"
    draw.rounded_rectangle((130, 112, 510, 158), radius=23, fill="#2a241d", outline="#6f5836")
    draw.text((320, 135), eyebrow.upper(), anchor="mm", font=font(20, True), fill=gold)
    title_font = font(76, True)
    y = 250
    for line in wrap(draw, title, title_font, 1500):
        draw.text((WIDTH // 2, y), line, anchor="ma", font=title_font, fill="#f6f0e7")
        y += 92
    subtitle_font = font(31)
    y += 28
    for line in wrap(draw, subtitle, subtitle_font, 1250):
        draw.text((WIDTH // 2, y), line, anchor="ma", font=subtitle_font, fill="#b8b2ac")
        y += 46
    draw.line((650, 825, 1270, 825), fill="#665744", width=2)
    draw.text((WIDTH // 2, 880), footer, anchor="ma", font=font(24), fill=gold)
    image.save(path)


def architecture_slide(path: Path) -> None:
    image = background()
    draw = ImageDraw.Draw(image)
    draw.text((100, 70), "Architektur", font=font(52, True), fill="#f6f0e7")
    draw.text((100, 136), "Klare Trennung von UI, API, KI-Logik und Persistenz", font=font(25), fill="#aaa4a0")

    boxes = [
        (90, 300, 390, 630, "Frontend", ["Vanilla HTML / CSS / JS", "DE / EN", "BYOK im Browser"], "#315f55"),
        (520, 250, 880, 680, "FastAPI", ["REST-Endpunkte", "Pydantic", "Orchestrierung"], "#765b2d"),
        (1010, 190, 1390, 440, "KI & RAG", ["Claude + OpenAI", "Few-shot + CoT", "Embeddings / TF-IDF"], "#58447a"),
        (1010, 520, 1390, 770, "Services", ["Datei-Extraktion", "ATS-Analyse", "PDF / DOCX"], "#2e557d"),
        (1510, 330, 1810, 640, "SQLite", ["sessions", "cv_documents", "generations", "messages"], "#7d4c2e"),
    ]
    for x1, y1, x2, y2, heading, lines, color in boxes:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=22, fill="#17161d", outline=color, width=4)
        draw.rectangle((x1, y1, x2, y1 + 65), fill=color)
        draw.text(((x1 + x2) // 2, y1 + 33), heading, anchor="mm", font=font(26, True), fill="#fff")
        y = y1 + 105
        for line in lines:
            draw.ellipse((x1 + 28, y - 4, x1 + 38, y + 6), fill="#e8b866")
            draw.text((x1 + 55, y), line, anchor="lm", font=font(21), fill="#d5d1cc")
            y += 54
    for start, end in [
        ((390, 465), (520, 465)),
        ((880, 430), (1010, 315)),
        ((880, 500), (1010, 645)),
        ((1390, 315), (1510, 430)),
        ((1390, 645), (1510, 540)),
    ]:
        draw.line((*start, *end), fill="#b6955d", width=5)
        ex, ey = end
        draw.polygon([(ex, ey), (ex - 18, ey - 10), (ex - 18, ey + 10)], fill="#b6955d")
    draw.text((100, 920), "Request-Ablauf", font=font(24, True), fill="#e8b866")
    flow = "Validieren  ->  RAG-Kontext  ->  Prompt  ->  Provider  ->  ATS-Analyse  ->  Speichern"
    draw.text((100, 970), flow, font=font(25), fill="#d5d1cc")
    image.save(path)


def technology_slide(path: Path) -> None:
    image = background()
    draw = ImageDraw.Draw(image)
    draw.text((100, 70), "Qualität, Sicherheit und Roadmap", font=font(52, True), fill="#f6f0e7")
    columns = [
        ("KI Engineering", ["2 Text-APIs", "RAG + Kontextinjektion", "Few-shot + Chain-of-Thought", "Conversation History"], "#58447a"),
        ("Datenschutz", ["API-Keys nie persistiert", "Keine erfundenen Fakten", "Demo-Modus ohne Key", "Kaskadierendes Loeschen"], "#315f55"),
        ("Nächste Schritte", ["PostgreSQL", "Alembic Migrationen", "Login und Nutzerkonten", "Tests und Docker"], "#765b2d"),
    ]
    x = 100
    for heading, lines, color in columns:
        draw.rounded_rectangle((x, 235, x + 500, 820), radius=24, fill="#17161d", outline=color, width=4)
        draw.rectangle((x, 235, x + 500, 315), fill=color)
        draw.text((x + 250, 275), heading, anchor="mm", font=font(27, True), fill="#fff")
        y = 390
        for line in lines:
            draw.ellipse((x + 46, y - 7, x + 60, y + 7), fill="#e8b866")
            draw.text((x + 90, y), line, anchor="lm", font=font(24), fill="#d5d1cc")
            y += 88
        x += 560
    draw.text(
        (WIDTH // 2, 930),
        "Vom lokalen MVP zur skalierbaren Multi-User-Anwendung",
        anchor="ma",
        font=font(28),
        fill="#b8b2ac",
    )
    image.save(path)


def framed_image(source: Path, destination: Path, title: str, subtitle: str = "") -> None:
    base = background()
    draw = ImageDraw.Draw(base)
    draw.text((85, 56), title, font=font(42, True), fill="#f6f0e7")
    if subtitle:
        draw.text((88, 110), subtitle, font=font(21), fill="#aaa4a0")
    with Image.open(source).convert("RGB") as source_image:
        max_w, max_h = 1710, 860
        source_image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        x = (WIDTH - source_image.width) // 2
        y = 170 + (860 - source_image.height) // 2
        draw.rounded_rectangle((x - 8, y - 8, x + source_image.width + 8, y + source_image.height + 8), radius=15, fill="#332d28")
        base.paste(source_image, (x, y))
    base.save(destination)


def make_slides() -> None:
    title_slide(
        ASSETS / "00-title.png",
        "Projektvorstellung",
        "Lebenslauf Boost AI",
        "KI-gestützte CV-Optimierung mit RAG, Modellvergleich und ATS-Analyse",
        "FastAPI  |  SQLite  |  Claude + OpenAI  |  PDF & Word",
    )
    architecture_slide(ASSETS / "06-architecture.png")
    framed_image(
        ROOT / "docs" / "schema.png",
        ASSETS / "07-database.png",
        "Datenmodell",
        "Vier Tabellen, vollständige Versionshistorie und Conversation History",
    )
    technology_slide(ASSETS / "08-quality.png")
    title_slide(
        ASSETS / "09-outro.png",
        "Fazit",
        "Vom Original-CV zum exportierbaren Entwurf",
        "Relevanter Kontext, transparenter KI-Vergleich und kontrollierbare Ergebnisse",
        "Lebenslauf Boost AI",
    )


def tts(scene: Scene, index: int) -> tuple[Path, float]:
    audio = BUILD / f"{index:02d}-{scene.key}.aiff"
    run(["say", "-v", "Anna", "-r", "155", "-o", str(audio), germanize(scene.narration)])
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(audio)],
        check=True,
        text=True,
        capture_output=True,
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
    return [chunk for chunk in chunks if chunk]


def write_subtitles(timed_scenes: list[tuple[Scene, float, float]]) -> Path:
    target = VIDEO_DIR / "lebenslauf-boost-ai-projektvideo.srt"
    entries: list[str] = []
    counter = 1
    for scene, start, duration in timed_scenes:
        chunks = subtitle_chunks(germanize(scene.narration))
        weights = [max(len(chunk), 20) for chunk in chunks]
        total_weight = sum(weights)
        cursor = start + 0.25
        usable = max(duration - 0.6, 0.5)
        for chunk, weight in zip(chunks, weights):
            chunk_duration = usable * weight / total_weight
            end = cursor + chunk_duration
            entries.append(f"{counter}\n{srt_time(cursor)} --> {srt_time(end)}\n{chunk}\n")
            counter += 1
            cursor = end
    target.write_text("\n".join(entries), encoding="utf-8")
    return target


def render_scene(scene: Scene, audio: Path, duration: float, index: int) -> Path:
    output = BUILD / f"{index:02d}-{scene.key}.mp4"
    final_duration = duration + 0.8
    fade_out = max(final_duration - 0.55, 0)
    video_filter = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"zoompan=z='min(zoom+0.00006,1.025)':d=1:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"fade=t=in:st=0:d=0.35,fade=t=out:st={fade_out:.3f}:d=0.5"
    )
    run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(scene.image), "-i", str(audio),
            "-vf", video_filter,
            "-af", f"afade=t=in:st=0:d=0.2,afade=t=out:st={max(duration - 0.35, 0):.3f}:d=0.3",
            "-t", f"{final_duration:.3f}",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(output),
        ]
    )
    return output


def build_video() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    make_slides()
    scenes = [
        Scene("title", ASSETS / "00-title.png", NARRATIONS["title"]),
        Scene("problem", ASSETS / "01-hero.png", NARRATIONS["problem"]),
        Scene("input", ASSETS / "02-input-upload.png", NARRATIONS["input"]),
        Scene("generation", ASSETS / "03-compare-output.png", NARRATIONS["generation"]),
        Scene("refine", ASSETS / "04-refine.png", NARRATIONS["refine"]),
        Scene("export", ASSETS / "05-design-export.png", NARRATIONS["export"]),
        Scene("architecture", ASSETS / "06-architecture.png", NARRATIONS["architecture"]),
        Scene("database", ASSETS / "07-database.png", NARRATIONS["database"]),
        Scene("quality", ASSETS / "08-quality.png", NARRATIONS["quality"]),
        Scene("outro", ASSETS / "09-outro.png", NARRATIONS["outro"]),
    ]

    rendered: list[Path] = []
    timed: list[tuple[Scene, float, float]] = []
    elapsed = 0.0
    for index, scene in enumerate(scenes, 1):
        audio, audio_duration = tts(scene, index)
        scene_duration = audio_duration + 0.8
        timed.append((scene, elapsed, scene_duration))
        rendered.append(render_scene(scene, audio, audio_duration, index))
        elapsed += scene_duration

    concat_file = BUILD / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in rendered),
        encoding="utf-8",
    )
    uncaptioned = BUILD / "project-video-uncaptioned.mp4"
    run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", "-movflags", "+faststart", str(uncaptioned),
        ]
    )

    subtitles = write_subtitles(timed)
    final = VIDEO_DIR / "lebenslauf-boost-ai-projektvideo.mp4"
    relative_subtitles = subtitles.relative_to(ROOT).as_posix()
    subtitle_filter = (
        f"subtitles=filename='{relative_subtitles}':"
        "force_style='FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00101010,BackColour=&H99000000,BorderStyle=3,"
        "Outline=1,Shadow=0,MarginV=38,Alignment=2'"
    )
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(uncaptioned), "-vf", subtitle_filter,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(final),
        ],
        cwd=ROOT,
        text=True,
    )
    if result.returncode != 0:
        print("Untertitel konnten nicht eingebrannt werden; liefere MP4 plus separate SRT.")
        shutil.copy2(uncaptioned, final)

    speaker_text = VIDEO_DIR / "sprechertext.txt"
    speaker_text.write_text(
        "\n\n".join(
            f"{index}. {scene.key.upper()}\n{germanize(scene.narration)}"
            for index, scene in enumerate(scenes, 1)
        ),
        encoding="utf-8",
    )
    print(f"\nFertig: {final}\nUntertitel: {subtitles}\nGeplante Laufzeit: {elapsed:.1f} Sekunden")


if __name__ == "__main__":
    build_video()
