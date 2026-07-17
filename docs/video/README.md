# Projektvideo – Lebenslauf Boost AI

## Fertige Dateien

- **Video:** [`lebenslauf-boost-ai-projektvideo.mp4`](lebenslauf-boost-ai-projektvideo.mp4)
- **Untertitel:** [`lebenslauf-boost-ai-projektvideo.srt`](lebenslauf-boost-ai-projektvideo.srt)
- **Sprechertext:** [`sprechertext.txt`](sprechertext.txt)
- **Reproduzierbarer Renderer:** [`make_video.py`](make_video.py)
- **Screenshot-Capture:** [`capture_screens.py`](capture_screens.py)

Die MP4- und SRT-Datei haben denselben Dateinamen. Videoplayer wie VLC laden
die deutschen Untertitel deshalb automatisch oder über **Untertitel → Datei
hinzufügen**.

## Technische Daten

- Laufzeit: ca. **4:48 Minuten**
- Auflösung: **1920 × 1080 (Full HD)**
- Bild: **H.264, 30 FPS**
- Ton: **AAC, 48 kHz**
- Sprache: **Deutsch**
- Format: **MP4**

## Kapitel

| Zeit | Inhalt |
|---|---|
| 00:00–00:26 | Titel: Sapphire Nightfall, Boosti, 6 Designs |
| 00:26–00:57 | Problem und Lösung |
| 00:57–01:30 | Stellenanzeige, CV-Upload, API-Key-Links und RAG |
| 01:30–02:02 | Professionelle Prompts, 5s-Laden, Vergleich & ATS |
| 02:02–02:27 | Iterative Verbesserung mit Conversation History |
| 02:27–02:57 | Sechs Designs, Vorschau und PDF/Word-Export |
| 02:57–03:28 | Technische Architektur |
| 03:28–04:03 | Datenbankmodell |
| 04:03–04:32 | Anforderungen, Sicherheit und Roadmap |
| 04:32–04:48 | Fazit |

## Gezeigte Demo

Das Video verwendet einen neutralen Musterlebenslauf und eine fiktive
Stellenanzeige. Die Generierung läuft bewusst im gekennzeichneten Demo-Modus,
damit keine privaten API-Schlüssel oder kostenpflichtigen Requests für die
Aufnahme benötigt werden. Screenshots stammen von der aktualisierten UI
(Boosti-Tour, Key-Links, sechs Export-Designs).

## Video neu erzeugen

Voraussetzungen auf macOS:

- Python-Umgebung des Projekts
- `ffmpeg` und `ffprobe`
- macOS-Sprachdienst `say` mit deutscher Stimme „Anna“
- Playwright (für frische Screenshots): `pip install playwright && playwright install chromium`

```bash
# optional: frische UI-Screenshots
.venv/bin/python docs/video/capture_screens.py

# Video, Untertitel und Sprechertext
.venv/bin/python docs/video/make_video.py
```

Der Renderer erstellt Folien, deutsche Sprachsegmente, animierte Szenen,
Untertitel, Sprechertext und die finale MP4-Datei reproduzierbar neu.
