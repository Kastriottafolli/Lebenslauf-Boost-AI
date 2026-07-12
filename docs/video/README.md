# Projektvideo – Lebenslauf Boost AI

## Fertige Dateien

- **Video:** [`lebenslauf-boost-ai-projektvideo.mp4`](lebenslauf-boost-ai-projektvideo.mp4)
- **Untertitel:** [`lebenslauf-boost-ai-projektvideo.srt`](lebenslauf-boost-ai-projektvideo.srt)
- **Sprechertext:** [`sprechertext.txt`](sprechertext.txt)
- **Reproduzierbarer Renderer:** [`make_video.py`](make_video.py)

Die MP4- und SRT-Datei haben denselben Dateinamen. Videoplayer wie VLC laden
die deutschen Untertitel deshalb automatisch oder über **Untertitel → Datei
hinzufügen**.

## Technische Daten

- Laufzeit: ca. **4:59 Minuten**
- Auflösung: **1920 × 1080 (Full HD)**
- Bild: **H.264, 30 FPS**
- Ton: **AAC, 48 kHz**
- Sprache: **Deutsch**
- Format: **MP4**

## Kapitel

| Zeit | Inhalt |
|---|---|
| 00:00–00:20 | Titel und Projektziel |
| 00:20–00:51 | Problem und Lösung |
| 00:51–01:24 | Stellenanzeige, CV-Upload und RAG |
| 01:24–02:00 | Claude/OpenAI-Vergleich und ATS-Analyse |
| 02:00–02:25 | Iterative Verbesserung mit Conversation History |
| 02:25–02:54 | Designs, Vorschau und PDF/Word-Export |
| 02:54–03:33 | Technische Architektur |
| 03:33–04:08 | Datenbankmodell |
| 04:08–04:42 | Anforderungen, Sicherheit und Roadmap |
| 04:42–04:59 | Fazit |

## Gezeigte Demo

Das Video verwendet einen neutralen Musterlebenslauf und eine fiktive
Stellenanzeige. Die Generierung läuft bewusst im gekennzeichneten Demo-Modus,
damit keine privaten API-Schlüssel oder kostenpflichtigen Requests für die
Aufnahme benötigt werden.

## Video neu erzeugen

Voraussetzungen auf macOS:

- Python-Umgebung des Projekts
- `ffmpeg` und `ffprobe`
- macOS-Sprachdienst `say` mit deutscher Stimme „Anna“

```bash
.venv/bin/python docs/video/make_video.py
```

Der Renderer erstellt Folien, deutsche Sprachsegmente, animierte Szenen,
Untertitel, Sprechertext und die finale MP4-Datei reproduzierbar neu.
