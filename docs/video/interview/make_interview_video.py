"""Studio-quality technical interview explainer video (English).

Realistic Edge TTS voiceover + Sapphire Nightfall motion slides.
Output: docs/video/interview/lebenslauf-boost-ai-technical-interview.mp4
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
VOICE = "en-US-AndrewMultilingualNeural"  # warm, confident, authentic

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


# ── Interview script (hire-me technical walkthrough) ──────────────────────────

SCENES: list[Scene] = [
    Scene(
        key="title",
        title="Lebenslauf Boost AI",
        subtitle="A technical walkthrough — architecture, APIs, prompts, and end-to-end flow",
        bullets=[],
        layout="title",
        narration=(
            "Hi — thank you for the opportunity to walk you through Lebenslauf Boost AI. "
            "This is a full-stack AI engineering project I built to optimize a real résumé "
            "against a specific job posting. In this video I'll explain how the frontend and backend work, "
            "which external APIs we call and why, how the prompt system is designed, "
            "and how the full pipeline runs from upload to export."
        ),
    ),
    Scene(
        key="pitch",
        title="What the product does",
        subtitle="Problem, solution, and design principles",
        bullets=[
            "Problem: generic CVs fail ATS filters and waste candidate time",
            "Solution: tailor a real CV to one job posting with grounded AI",
            "Truthfulness first — never invent employers, degrees, or metrics",
            "Dual providers: Anthropic Claude and OpenAI, with side-by-side compare",
            "End-to-end: upload → RAG → generate → refine → PDF/Word export",
        ],
        narration=(
            "At a high level, the product solves a practical hiring problem. "
            "Candidates need their résumé rewritten for each job, but unconstrained generative AI "
            "often invents skills or achievements. Our design principle is truthfulness first: "
            "the model may only use facts from the uploaded CV. "
            "We retrieve the most relevant CV sections with RAG, generate one or two drafts with Claude and OpenAI, "
            "score them against the job keywords, let the user refine the text, "
            "and export a polished PDF or Word file in one of six designs."
        ),
    ),
    Scene(
        key="architecture",
        title="System architecture",
        subtitle="Clear separation of UI, API, AI, and persistence",
        bullets=[
            "Frontend: vanilla ES modules — Sapphire Nightfall UI + Boosti tour",
            "Backend: FastAPI routers → services → LLM provider layer",
            "Prompts: editable text templates under prompts/, loaded with cache",
            "Persistence: SQLite via SQLAlchemy — sessions, CV, generations, messages",
            "Graceful fallbacks: embeddings → TF-IDF, live API → labeled demo mode",
        ],
        layout="diagram",
        narration=(
            "Architecturally, I kept the system intentionally modular. "
            "The frontend is a lightweight vanilla JavaScript SPA — no React build step — "
            "styled in a custom Sapphire Nightfall design system, with Boosti, an animated guide that walks users through the flow. "
            "The backend is FastAPI with thin routers and thicker services. "
            "LLM access goes through a provider abstraction so Claude and OpenAI share the same interface. "
            "Prompt text lives outside the code as German and English template files, "
            "so prompt engineering can evolve without touching Python. "
            "SQLite stores sessions and history. And when keys or embeddings are missing, "
            "the app degrades gracefully into a clearly labeled demo mode instead of failing."
        ),
    ),
    Scene(
        key="frontend",
        title="Frontend — how the UI works",
        subtitle="Three steps, BYOK keys, i18n, and client orchestration",
        bullets=[
            "Step 1 Input: job posting, wishes, CV upload, provider, technique",
            "Step 2 Edit: markdown editor, compare cards, ATS chips, refine",
            "Step 3 Design: six themes, live preview, PDF or DOCX download",
            "BYOK: API keys stay in browser localStorage — never saved in the DB",
            "api.js talks to /api/session, upload-cv, generate, refine, export",
        ],
        screenshot=ASSETS_UI / "01-hero.png",
        layout="split",
        narration=(
            "On the frontend, the experience is a three-step wizard. "
            "Step one collects the job description, optional wishes, the CV file, "
            "the provider choice — Claude, OpenAI, or compare — and the prompt technique. "
            "Step two is the editing surface: the generated markdown, a compare bar when both models run, "
            "an ATS keyword panel, and refine chips like shorter or more formal. "
            "Step three is design and download with six visual themes. "
            "API keys follow a bring-your-own-key model: they live only in localStorage, "
            "are attached to each request, and are never persisted server-side. "
            "All network calls go through a small api.js module with timeouts on generation."
        ),
    ),
    Scene(
        key="backend",
        title="Backend — request path",
        subtitle="Routers, services, and the LLM layer",
        bullets=[
            "routers/: HTTP only — sessions, documents, generations, exports",
            "services/: extraction, RAG, generation orchestration, export",
            "llm/: AnthropicProvider, OpenAIProvider, shared LLMResult",
            "Pydantic schemas validate every payload before business logic",
            "One session hubs CV document, generations, and chat messages",
        ],
        narration=(
            "On the backend, I separated HTTP from business logic. "
            "Routers handle sessions, document upload, generation, refine, and export. "
            "Services own the real work: file extraction from PDF, DOCX, or text, "
            "RAG indexing and retrieval, generation orchestration, and PDF or Word rendering. "
            "The LLM package defines an abstract provider, then concrete Anthropic and OpenAI implementations "
            "that both return a structured result with content, model name, and demo flag. "
            "Pydantic validates every request. "
            "A session is the hub: at most one CV document, many generations, and a message history used for refine."
        ),
    ),
    Scene(
        key="apis",
        title="External APIs — what we call and how",
        subtitle="Anthropic Messages API + OpenAI Chat & Embeddings",
        bullets=[
            "Anthropic: messages.create — system prompt + user/assistant turns",
            "OpenAI Chat: chat.completions.create — same logical roles",
            "OpenAI Embeddings: text-embedding-3-small for RAG vectors",
            "Key precedence: UI BYOK key → server .env key → demo fallback",
            "Compare mode calls both providers independently, then ranks by ATS",
        ],
        narration=(
            "We use two different text-generation APIs, which was an explicit project requirement. "
            "For Claude, we call Anthropic's Messages API with a system prompt and a message list. "
            "For OpenAI, we call Chat Completions with the same logical roles, "
            "and separately we use OpenAI embeddings — text-embedding-3-small — to vectorize CV chunks for RAG. "
            "Key resolution is important for privacy and demos: "
            "a key typed in the UI wins, otherwise we fall back to a server environment key, "
            "and if neither exists we return a labeled demo résumé so the full product flow still works. "
            "In compare mode, both providers run independently; we do not ask one model to judge the other. "
            "Instead we rank drafts with our own ATS keyword overlap score."
        ),
    ),
    Scene(
        key="prompts",
        title="Prompt engineering system",
        subtitle="Twelve templates · four techniques · one assembly pipeline",
        bullets=[
            "12 template files: 6 roles × German and English",
            "Role prompting: senior résumé writer + ATS specialist persona",
            "Few-shot: weak → strong bullet rewrites with metric discipline",
            "Chain-of-thought: 7 internal analysis steps — never printed",
            "Format constraints + dynamic context injection of RAG chunks",
            "auto technique = few-shot AND chain-of-thought together",
        ],
        narration=(
            "The prompt system is one of the parts I'm most intentional about. "
            "There are twelve template files under the prompts folder — six logical roles, each in German and English: "
            "system role, few-shot examples, chain-of-thought instructions, output format, the user message shell, and refine. "
            "Role prompting sets a senior executive résumé writer who must stay factual. "
            "Few-shot shows weak versus strong bullets so the model learns impact writing without inventing numbers. "
            "Chain-of-thought forces a private seven-step analysis — job requirements, evidence mapping, keyword plan — "
            "but those steps are never shown to the user. "
            "Format constraints lock the markdown structure. "
            "And dynamic context injection fills the user message with the job posting, wishes, and retrieved CV excerpts. "
            "When technique is set to auto, we combine few-shot and chain-of-thought in one prompt."
        ),
    ),
    Scene(
        key="pipeline",
        title="End-to-end generation pipeline",
        subtitle="From upload to ATS-scored draft",
        bullets=[
            "1. Extract text and optional photo from PDF / DOCX / TXT",
            "2. Chunk ~700 chars, embed or TF-IDF index, store on session",
            "3. Retrieve top-k chunks for the job + wishes query",
            "4. Assemble system + technique + format + injected context",
            "5. Call provider(s), score keywords, persist generation + messages",
        ],
        screenshot=ASSETS_UI / "03-compare-output.png",
        layout="split",
        narration=(
            "Here is the generation pipeline in order. "
            "First, upload extracts text and optionally a photo. "
            "Second, we chunk the CV — about seven hundred characters with overlap — "
            "and build an index with embeddings when an OpenAI key is available, otherwise pure-Python TF-IDF. "
            "Third, at generate time we retrieve the top chunks most relevant to the job description and wishes. "
            "Fourth, prompts.py assembles the system persona, the selected technique blocks, the format rules, "
            "and the injected RAG context. "
            "Fifth, we call one or both providers, run ATS keyword analysis against the job posting, "
            "and persist each draft plus the conversation messages for later refine."
        ),
    ),
    Scene(
        key="refine_export",
        title="Refine, compare, and export",
        subtitle="Conversation history and six design themes",
        bullets=[
            "Refine sends last user + assistant + new instruction",
            "Each refine creates a new generation row — history is kept",
            "Compare UI surfaces winner by ATS score, user can override",
            "Export is stateless: markdown + design + format in the request",
            "Six designs: Azure, Executive, Nordic, Sapphire, Cobalt, Slate",
        ],
        screenshot=ASSETS_UI / "05-design-export.png",
        layout="split",
        narration=(
            "After the first draft, refine uses conversation history. "
            "We send the previous user message, the assistant draft, and a new instruction — "
            "for example make it shorter or more technical — then store a new generation with technique refine. "
            "Nothing is overwritten, so versions remain auditable. "
            "In compare mode the UI highlights the higher ATS score, but the user can pick either draft. "
            "Export is intentionally stateless: the client sends the final markdown, design, format, and optional photo. "
            "ReportLab and python-docx render six visual themes without writing files into the database."
        ),
    ),
    Scene(
        key="quality",
        title="Quality, security, and trade-offs",
        subtitle="What I would emphasize in a hiring interview",
        bullets=[
            "Privacy: BYOK keys never land in SQLite",
            "Reliability: demo mode keeps the UX testable without paid keys",
            "Evaluation: ATS overlap is an application-specific metric",
            "Maintainability: prompts as files, providers behind an ABC",
            "Next: PostgreSQL, Alembic, auth, tests, and Docker",
        ],
        narration=(
            "If I were summarizing engineering judgment for a hiring conversation, I'd highlight four things. "
            "Privacy: user keys stay in the browser. "
            "Reliability: demo mode means reviewers can exercise the full flow without credentials. "
            "Evaluation: we measure fit with an application-specific ATS keyword score, not vague vibes. "
            "And maintainability: prompts are data, providers are swappable, routers stay thin. "
            "The honest next steps for production would be PostgreSQL with Alembic, real authentication, "
            "broader automated tests, and containerized deployment."
        ),
    ),
    Scene(
        key="outro",
        title="Thank you",
        subtitle="Lebenslauf Boost AI — grounded generation, dual APIs, end-to-end product thinking",
        bullets=[],
        layout="outro",
        narration=(
            "That's the system end to end: a product-shaped AI workflow with clear architecture, "
            "two real model providers, a structured prompt stack, retrieval grounding, and a complete user journey "
            "from upload to export. Happy to go deeper on any layer — prompts, RAG, or the FastAPI service design. "
            "Thank you for watching."
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
    draw.text((245, 70), "TECHNICAL WALKTHROUGH", anchor="mm", font=font(15, True), fill="#fff")
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
        draw.text((960, 730), "Interview-style explainer", anchor="mm", font=font(20, True), fill="#fff")

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


async def synthesize(text: str, dest: Path) -> float:
    dest.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, VOICE, rate="-5%", pitch="-2Hz")
    await communicate.save(str(dest))
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(dest)],
        check=True, text=True, capture_output=True,
    )
    return float(probe.stdout.strip())


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
        cursor = start + 0.2
        usable = max(dur - 0.5, 0.4)
        for chunk, w in zip(chunks, weights):
            end = cursor + usable * w / total
            entries.append(f"{n}\n{srt_time(cursor)} --> {srt_time(end)}\n{chunk}\n")
            n += 1
            cursor = end
    path.write_text("\n".join(entries), encoding="utf-8")


def render_clip(image: Path, audio: Path, duration: float, dest: Path) -> None:
    final = duration + 0.55
    fade_out = max(final - 0.45, 0)
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"zoompan=z='min(zoom+0.00004,1.018)':d=1:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"fade=t=in:st=0:d=0.35,fade=t=out:st={fade_out:.3f}:d=0.4"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
            "-vf", vf,
            "-af", f"afade=t=in:st=0:d=0.15,afade=t=out:st={max(duration-0.25,0):.3f}:d=0.22,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-t", f"{final:.3f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "slow", "-crf", "16",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
            "-movflags", "+faststart", str(dest),
        ],
        check=True,
    )


async def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    total = len(SCENES)
    timed: list[tuple[Scene, float, float]] = []
    clips: list[Path] = []
    elapsed = 0.0

    script_lines = []
    for i, scene in enumerate(SCENES, 1):
        print(f"[{i}/{total}] {scene.key}")
        img = render_scene_image(scene, i, total)
        audio = BUILD / f"{i:02d}-{scene.key}.mp3"
        dur = await synthesize(scene.narration, audio)
        clip = BUILD / f"{i:02d}-{scene.key}.mp4"
        render_clip(img, audio, dur, clip)
        scene_dur = dur + 0.55
        timed.append((scene, elapsed, scene_dur))
        clips.append(clip)
        elapsed += scene_dur
        script_lines.append(f"{i}. {scene.key.upper()} — {scene.title}\n{scene.narration}\n")

    concat = BUILD / "concat.txt"
    concat.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips), encoding="utf-8")
    final = OUT / "lebenslauf-boost-ai-technical-interview.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(final)],
        check=True,
    )
    srt = OUT / "lebenslauf-boost-ai-technical-interview.srt"
    write_srt(timed, srt)
    (OUT / "sprechertext.md").write_text(
        "# Technical Interview Explainer — Narration\n\n"
        f"Voice: `{VOICE}` via edge-tts\n"
        f"Duration target: ~{elapsed/60:.1f} minutes\n\n"
        + "\n".join(script_lines),
        encoding="utf-8",
    )
    (OUT / "README.md").write_text(
        "# Technical Interview Explainer Video\n\n"
        "Professional English walkthrough of Lebenslauf Boost AI — architecture, APIs, prompts, and product flow.\n\n"
        f"- **Video:** [`lebenslauf-boost-ai-technical-interview.mp4`](lebenslauf-boost-ai-technical-interview.mp4)\n"
        f"- **Subtitles:** [`lebenslauf-boost-ai-technical-interview.srt`](lebenslauf-boost-ai-technical-interview.srt)\n"
        f"- **Script:** [`sprechertext.md`](sprechertext.md)\n"
        f"- **Voice:** `{VOICE}` (Edge TTS neural)\n\n"
        "Regenerate:\n\n```bash\n.venv/bin/python docs/video/interview/make_interview_video.py\n```\n",
        encoding="utf-8",
    )
    print(f"\nDone: {final}\nDuration: {elapsed:.1f}s ({elapsed/60:.1f} min)\nSubtitles: {srt}")


if __name__ == "__main__":
    asyncio.run(build())
