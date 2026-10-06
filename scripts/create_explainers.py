"""Render local branded explainers from already generated voiceovers.

No API credentials are read. Artwork and fonts are local. The instrumental bed
and transition sounds are composed here; no third-party recording is sampled.
"""

import argparse
import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS = 1280, 720, 24
LANG = {
    "de": {
        "head": [
            "Dein nächster Job\nbeginnt mit dir.",
            "Dein Konto.\nDeine Unterlagen.",
            "Deine Erfahrung\ntrifft die passende Stelle.",
            "Vier Dokumente.\nEine Bewerbungsmappe.",
            "Prüfen. Gestalten.\nBereit zum Bewerben.",
            "Deine Zukunft.\nDein Boost.",
        ],
        "body": [
            "Boosty begleitet dich – vom Lebenslauf bis zur Bewerbung.",
            "Konto erstellen · E-Mail bestätigen · Sicher anmelden",
            "Lebenslauf hochladen und Stellenlink oder Stellentext hinzufügen.",
            "Lebenslauf · Anschreiben · Motivation · Bewerbungs-E-Mail",
            "Angaben prüfen, Design auswählen und als PDF oder Word herunterladen.",
            "3 Bewerbungen pro Woche kostenlos\ntafolliboost.com",
        ],
        "docs": ["Lebenslauf", "Anschreiben", "Motivation", "E-Mail"],
        "steps": ["Konto", "Unterlagen", "Stelle", "Mappe", "Export"],
        "verified": "E-Mail bestätigt",
        "job": "Deine Stellenanzeige",
        "name": "Dein Name",
        "role": "Deine Erfahrung",
        "check": "Dein letzter Check",
        "end": "Jetzt kostenlos starten",
        "sentences": [
            "Dein nächster Job beginnt mit dir.",
            "Erstelle dein Konto bei TafolliBoost und bestätige deine E-Mail.",
            "Lade deinen Lebenslauf hoch und füge die Stellenanzeige ein.",
            "Boosty erstellt deinen Lebenslauf, dein Anschreiben, dein Motivationsschreiben und deine Bewerbungs-E-Mail.",
            "Prüfe deine Angaben, wähle dein Design und lade deine Unterlagen herunter.",
            "Drei Bewerbungen pro Woche sind kostenlos.",
            "Starte jetzt auf TafolliBoost Punkt com.",
        ],
    },
    "en": {
        "head": [
            "Your next job\nstarts with you.",
            "Your account.\nYour documents.",
            "Your experience.\nThe right opportunity.",
            "Four documents.\nOne application package.",
            "Review. Design.\nReady to apply.",
            "Your future.\nYour boost.",
        ],
        "body": [
            "Boosty guides you from your résumé to your application.",
            "Create an account · Verify your email · Sign in securely",
            "Upload your résumé and add the job link or job text.",
            "Résumé · Cover letter · Motivation letter · Application email",
            "Check your details, pick a design, and download PDF or Word.",
            "3 free applications every week\ntafolliboost.com",
        ],
        "docs": ["Résumé", "Cover letter", "Motivation", "Email"],
        "steps": ["Account", "Documents", "Job", "Package", "Export"],
        "verified": "Email verified",
        "job": "Your job advert",
        "name": "Your name",
        "role": "Your experience",
        "check": "Your final review",
        "end": "Start for free",
        "sentences": [
            "Your next job starts with you.",
            "Create your TafolliBoost account and verify your email.",
            "Upload your résumé and add the job advert.",
            "Boosty prepares your résumé, cover letter, motivation letter, and application email.",
            "Review your details, choose your design, and download your documents.",
            "Three applications every week are free.",
            "Get started at TafolliBoost dot com.",
        ],
    },
    "sq": {
        "head": [
            "Puna jote e ardhshme\nfillon me ty.",
            "Llogaria jote.\nDokumentet e tua.",
            "Përvoja jote.\nMundësia e duhur.",
            "Katër dokumente.\nNjë dosje aplikimi.",
            "Kontrollo. Zgjidh.\nGati për aplikim.",
            "E ardhmja jote.\nBoost-i yt.",
        ],
        "body": [
            "Boosty të udhëzon nga CV-ja deri tek aplikimi.",
            "Krijo llogarinë · Konfirmo emailin · Hyr në mënyrë të sigurt",
            "Ngarko CV-në dhe shto lidhjen ose tekstin e njoftimit të punës.",
            "CV · Letër aplikimi · Letër motivimi · Email aplikimi",
            "Kontrollo të dhënat, zgjidh dizajnin dhe shkarko PDF ose Word.",
            "3 aplikime falas çdo javë\ntafolliboost.com",
        ],
        "docs": ["CV", "Letër aplikimi", "Motivimi", "Email"],
        "steps": ["Llogaria", "Dokumentet", "Puna", "Dosja", "Shkarkimi"],
        "verified": "Emaili u konfirmua",
        "job": "Njoftimi i punës",
        "name": "Emri yt",
        "role": "Përvoja jote",
        "check": "Kontrolli i fundit",
        "end": "Fillo falas",
        "sentences": [
            "Puna jote e ardhshme fillon me ty.",
            "Krijo llogarinë tënde në TafolliBoost dhe konfirmo emailin.",
            "Ngarko CV-në dhe shto njoftimin e punës.",
            "Boosty përgatit CV-në, letrën e aplikimit, letrën e motivimit dhe emailin e aplikimit.",
            "Kontrollo të dhënat, zgjidh dizajnin dhe shkarko dokumentet.",
            "Tre aplikime çdo javë janë falas.",
            "Fillo tani në TafolliBoost pikë com.",
        ],
    },
}


def font(size, bold=False):
    return ImageFont.truetype(
        str(ROOT / "static/fonts" / ("NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf")), size
    )


def wrapped(draw, text, xy, width, size=24, fill="#52627b", bold=False, spacing=10):
    f = font(size, bold)
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = (line + " " + word).strip()
            if draw.textlength(candidate, font=f) > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    for i, line in enumerate(lines):
        draw.text((xy[0], xy[1] + i * (size + spacing)), line, font=f, fill=fill)


def ease(x):
    x = max(0, min(1, x))
    return 1 - (1 - x) ** 3


def audio_bed(path, duration, transitions):
    sr = 48000
    t = np.arange(int(duration * sr)) / sr
    mix = np.zeros(len(t))
    beat = 60 / 104
    # A soft, original Cmaj7–Am7–Fmaj7–G6 arpeggio with no vocal samples.
    chords = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 64]]
    for step, start in enumerate(np.arange(0, duration, beat / 2)):
        chord = chords[int(start / (beat * 4)) % 4]
        note = chord[step % 4]
        freq = 440 * 2 ** ((note - 69) / 12)
        end = min(len(t), int((start + 1.4) * sr))
        begin = int(start * sr)
        dt = t[begin:end] - start
        env = (1 - np.exp(-dt * 45)) * np.exp(-dt * 3)
        mix[begin:end] += (
            0.017 * env * (np.sin(2 * np.pi * freq * dt) + 0.22 * np.sin(2 * np.pi * freq * 2 * dt))
        )
    rng = np.random.default_rng(23)
    for start in transitions:
        begin = int(start * sr)
        end = min(len(t), int((start + 0.26) * sr))
        dt = t[begin:end] - start
        whoosh = rng.normal(0, 1, len(dt))
        whoosh = np.convolve(whoosh, np.ones(20) / 20, mode="same")
        env = np.sin(np.pi * np.minimum(dt / 0.26, 1)) ** 2
        mix[begin:end] += 0.035 * whoosh * env + 0.012 * np.sin(
            2 * np.pi * (920 * dt + 180 * dt**2)
        ) * np.exp(-dt * 14)
    fade = np.minimum(1, t / 0.8) * np.minimum(1, (duration - t) / 1.1)
    mix *= fade
    samples = np.clip(mix, -1, 1)
    pcm = (np.stack([samples, samples], axis=-1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(pcm.tobytes())


def timestamp(t):
    ms = round(t * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"


def render(lang, voice_dir, output):
    copy = LANG[lang]
    voice = voice_dir / f"voice-{lang}.mp3"
    duration = float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(voice),
            ]
        )
    )
    total = max(27, min(30, duration + 0.09))
    scale = total / duration if duration > total else 1
    # Narration sentence-length weights place scene cuts at the main spoken ideas.
    weights = [len(s) for s in copy["sentences"]]
    bounds = [0]
    for weight in weights:
        bounds.append(bounds[-1] + weight / sum(weights) * duration * scale)
    cuts = [0, bounds[1], bounds[2], bounds[3], bounds[4], bounds[5]]
    mascot = Image.open(ROOT / "static/boosty-3d.png").convert("RGBA")
    bbox = mascot.getbbox()
    mascot = mascot.crop(bbox).resize((365, 365), Image.Resampling.LANCZOS)
    # Antialiased frames use a static gradient and animated vector cards/mascot.
    yy = np.linspace(0, 1, H)[:, None, None]
    top = np.array([247, 250, 255])
    bottom = np.array([231, 240, 255])
    background = np.tile((top * (1 - yy) + bottom * yy).astype("uint8"), (1, W, 1))
    video = voice_dir / f"visual-{lang}.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "24",
        "-pix_fmt",
        "yuv420p",
        str(video),
    ]
    pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def frame(t):
        image = Image.fromarray(background.copy()).convert("RGBA")
        d = ImageDraw.Draw(image)
        stage = max(i for i, start in enumerate(cuts) if t >= start)
        local = t - cuts[stage]
        entry = ease(local / 0.6)
        d.ellipse((815, 115, 1260, 560), outline="#d1e1f8", width=2)
        for i in range(3):
            angle = t * 0.23 + i * 2.1
            x = 1038 + 218 * math.cos(angle)
            y = 337 + 218 * math.sin(angle)
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill="#b4d9ef")
        d.text((66, 37), "tafolliboost.com", font=font(25, True), fill="#17304d")
        d.rounded_rectangle((1048, 34, 1215, 74), radius=20, fill="#e3edfd")
        d.text(
            (1073, 44),
            {"de": "MIT BOOSTY", "en": "WITH BOOSTY", "sq": "ME BOOSTY"}[lang],
            font=font(15, True),
            fill="#3168af",
        )
        tx = 70 - int((1 - entry) * 30)
        wrapped(d, copy["head"][stage], (tx, 161), 760, 48, "#172b48", True, 12)
        wrapped(d, copy["body"][stage], (tx, 330), 680, 25, spacing=13)
        # Timeline stays descriptive, rather than presenting a fictitious ATS score.
        for i, label in enumerate(copy["steps"]):
            x = 70 + i * 133
            active = i <= min(4, stage)
            d.ellipse((x, 530, x + 24, 554), fill="#326fc5" if active else "#ccd9eb")
            if i < stage:
                d.line([(x + 6, 542), (x + 10, 546), (x + 18, 537)], fill="white", width=2)
            else:
                d.text((x + 7, 533), str(i + 1), font=font(12, True), fill="white")
            d.text((x, 565), label, font=font(15), fill="#28548b" if active else "#6d7f97")
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        mx = 860 + int(math.sin(t * 1.8) * 8)
        my = 230 + int(math.sin(t * 2) * 9)
        ld.ellipse((920, 586, 1175, 626), fill=(57, 108, 170, 28))
        layer.alpha_composite(mascot, (mx, my))
        if stage == 1:
            ld.rounded_rectangle(
                (817, 163, 1217, 242), radius=22, fill="white", outline="#dce8f7", width=2
            )
            ld.ellipse((846, 185, 883, 222), fill="#d8f2e7")
            ld.line([(854, 202), (863, 211), (878, 192)], fill="#188967", width=3)
            ld.text((897, 190), copy["verified"], font=font(20, True), fill="#254267")
        elif stage == 2:
            for i, label in enumerate([copy["docs"][0], copy["job"]]):
                x = 802 + i * 218
                y = 174 - i * 13
                ld.rounded_rectangle(
                    (x, y, x + 205, y + 117), radius=19, fill="white", outline="#dce8f7", width=2
                )
                wrapped(ld, label, (x + 18, y + 19), 170, 18, "#254267", True, 4)
                for j in range(3):
                    ld.rounded_rectangle(
                        (x + 18, y + 60 + j * 12, x + 165 - j * 22, y + 65 + j * 12),
                        radius=2,
                        fill="#e3ebf5",
                    )
        elif stage == 3:
            for i, label in enumerate(copy["docs"]):
                x = 808 + (i % 2) * 203
                y = 134 + (i // 2) * 97
                dy = int(18 * (1 - ease((local - i * 0.17) / 0.4)))
                ld.rounded_rectangle(
                    (x, y + dy, x + 190, y + dy + 82),
                    radius=18,
                    fill="white",
                    outline="#dce8f7",
                    width=2,
                )
                wrapped(ld, label, (x + 16, y + dy + 18), 164, 17, "#254267", True, 3)
                ld.line([(x + 17, y + dy + 59), (x + 22, y + dy + 64), (x + 32, y + dy + 52)], fill="#188967", width=3)
        elif stage == 4:
            ld.rounded_rectangle(
                (834, 159, 1216, 270), radius=22, fill="white", outline="#dce8f7", width=2
            )
            ld.text((853, 178), copy["check"], font=font(20, True), fill="#254267")
            for i, label in enumerate(["PDF", "Word"]):
                ld.rounded_rectangle(
                    (853 + i * 168, 218, 1003 + i * 168, 255), radius=12, fill="#e8f0ff"
                )
                ld.text((898 + i * 168, 226), label, font=font(16, True), fill="#3168af")
        elif stage == 5:
            ld.rounded_rectangle((70, 427, 410, 487), radius=16, fill="#3168c3")
            ld.text((97, 444), copy["end"] + " →", font=font(21, True), fill="white")
        image = Image.alpha_composite(image, layer)
        d = ImageDraw.Draw(image)
        d.line((70, 640, 1215, 640), fill="#d5e2f3", width=2)
        d.text(
            (70, 661),
            {
                "de": "Deine Angaben. Dein letzter Check. Deine nächste Chance.",
                "en": "Your experience. Your final review. Your next opportunity.",
                "sq": "Të dhënat e tua. Kontrolli yt. Mundësia jote e ardhshme.",
            }[lang],
            font=font(17),
            fill="#526c8e",
        )
        d.text((1106, 661), f"{int(t):02}s / {math.ceil(total):02}s", font=font(15), fill="#6681a5")
        return image.convert("RGB")

    try:
        for i in range(math.ceil(total * FPS)):
            pipe.stdin.write(frame(i / FPS).tobytes())
    finally:
        pipe.stdin.close()
    if pipe.wait() != 0:
        raise RuntimeError("Video encoder failed")
    poster = frame(0.95)
    poster.save(output / f"tafolliboost-poster-{lang}.jpg", quality=88, optimize=True)
    bed = voice_dir / f"music-{lang}.wav"
    audio_bed(bed, total, cuts[1:])
    target = output / f"tafolliboost-{lang}.mp4"
    tempo = f",atempo={1 / scale}" if scale != 1 else ""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(video),
            "-i",
            str(voice),
            "-i",
            str(bed),
            "-filter_complex",
            f"[1:a]loudnorm=I=-16:LRA=7:TP=-1.5{tempo},apad[voice];[voice][2:a]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.89[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-t",
            str(total),
            "-movflags",
            "+faststart",
            str(target),
        ],
        check=True,
    )
    vtt = ["WEBVTT", ""]
    for i, sentence in enumerate(copy["sentences"]):
        vtt += [
            str(i + 1),
            timestamp(bounds[i]) + " --> " + timestamp(min(total, bounds[i + 1])),
            sentence,
            "",
        ]
    (output / f"tafolliboost-{lang}.vtt").write_text("\n".join(vtt), encoding="utf8")
    return {
        "language": lang,
        "duration_seconds": round(total, 3),
        "width": W,
        "height": H,
        "fps": FPS,
        "voice": "AI-generated",
        "music": "Original locally composed instrumental; no third-party samples",
        "bytes": target.stat().st_size,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice-dir", type=Path, required=True)
    parser.add_argument("--language", choices=["de", "en", "sq", "all"], default="all")
    args = parser.parse_args()
    output = ROOT / "static/video"
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for language in LANG if args.language == "all" else [args.language]:
        records.append(render(language, args.voice_dir, output))
        print(language + " explainer finished", flush=True)
    (output / "credits.json").write_text(
        json.dumps(
            {
                "project": "TafolliBoost explainer",
                "created": "2026-10-06",
                "artwork": "Existing Boosty artwork and brand graphics",
                "font_license": "Noto Sans, SIL Open Font License",
                "videos": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
