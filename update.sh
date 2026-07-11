#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Ein Befehl: alle Änderungen committen & zu GitHub hochladen.
#  Nutzung:   ./update.sh "Beschreibung der Änderung"
#  Ohne Text: ./update.sh          → Commit-Nachricht "Update"
# ─────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

MSG="${1:-Update}"

git add -A

if git diff --cached --quiet; then
  echo "ℹ️  Keine Änderungen — nichts zu committen."
else
  git commit -m "$MSG"
  echo "✓ Commit erstellt: $MSG"
fi

git push
echo "✓ Auf GitHub aktuell → https://github.com/Kastriottafolli/Lebenslauf-Boost-AI"
