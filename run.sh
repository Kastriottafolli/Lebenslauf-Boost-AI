#!/usr/bin/env bash
# Startet Lebenslauf Boost AI lokal.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "→ Erstelle virtuelle Umgebung …"
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "→ Installiere Abhängigkeiten …"
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "→ .env aus Vorlage erstellt — bitte API-Keys eintragen (sonst Demo-Modus)."
fi

echo "→ Starte Server auf http://127.0.0.1:8000"
uvicorn backend.main:app --reload
