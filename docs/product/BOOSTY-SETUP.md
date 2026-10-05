# Boosty: eigener OpenAI-Zugang, Softwarehilfe und Feldbegleitung

Die Hilfe verwendet ausschließlich `BOOSTY_OPENAI_API_KEY`. Sie liest keine Benutzer-Keys aus Schritt 3 und keinen allgemeinen `OPENAI_API_KEY`. Dieser Betreiber-Key wird von Lebenslauf-, Brief-, Vergleichs- und Revisionsendpunkten nicht verwendet. Die lokale Hilfe bleibt ohne Key verfügbar. Der Browser erhält niemals den Betreiber-Key.

## Sichere Vorbereitung

1. Im OpenAI-Dashboard ein eigenes Projekt nur für Boosty anlegen. Einen eingeschränkten Projekt-Key mit dem benötigten Zugriff auf Responses erstellen; unbenötigte Endpunkte sperren. Projektbudget und Benachrichtigungen prüfen. Ein Dashboard-Budgetalarm ist nicht automatisch eine harte Ausgabensperre.
2. Den Key **selbst lokal** in die private `.env` beziehungsweise auf dem Hostingserver in `.env.production` als `BOOSTY_OPENAI_API_KEY` eintragen. Nicht in einen Chat, Git, das Nutzer-Key-Feld oder Frontendcode kopieren. Datei-/Serverzugriff einschränken. Ein Secret-Manager kann die Umgebungsvariable statt einer Datei bereitstellen.
3. `BOOSTY_ENABLED=true` und `BOOSTY_OPENAI_MODEL=gpt-6-luna` setzen. Allgemeine Server-Keys weiterhin deaktiviert lassen (`ALLOW_SERVER_KEYS=false`). Server neu starten. Vor öffentlicher Aktivierung tatsächlichen Vertrag, Auftragsverarbeitung und Datenübermittlung dokumentieren.
4. In Boostys Hilfedialog erscheint „OpenAI-Softwarehilfe bereit“. Nutzer erlauben die Übermittlung ihrer Frage gesondert. Für die normale lokale Hilfe ist das nicht nötig.
5. Eine Softwarefrage und eine fachfremde Frage prüfen, Limits und Anbieterabrechnung beobachten. Der Live-Test wurde noch nicht durchgeführt; alle Anbietertests verwenden synthetische Keys und Mock-Antworten.

## Grenzen und Kostenkontrolle

Die KI **klassifiziert ausschließlich** ein Hilfethema aus einer festen Liste. Zur Anzeige kommen geprüfte Hilfetexte in DE/EN/SQ; freie KI-Texte, HTML, Code und vom Modell vorgeschlagene Befehle werden nicht angezeigt. Unbekannte oder fehlerhafte Antworten führen zu einer begrenzten Hilfe bzw. zu einem Hinweis auf die lokale Hilfe. Eine falsche Themenzuordnung bleibt möglich und muss mit realen Fragen geprüft werden.

Nur die aktuelle Frage (höchstens 2000 Zeichen) und eine feste Themenbeschreibung gehen an OpenAI. Kein CV, Profil, Kontodatensatz, Key oder Chatverlauf wird angehängt. Responses verwendet `store=false`, `max_output_tokens=256`, keine Tools und bei GPT-6 `reasoning.effort=none`. Das schaltet Anbieter-Missbrauchsprotokolle nicht automatisch ab.

Standardlimits: 500 KI-Fragen pro UTC-Tag für den gesamten Dienst und 20 pro Arbeitssitzung. Zähler werden vor dem Aufruf atomar reserviert, auch bei fehlgeschlagenen Aufrufen nicht erstattet und bis zu 30 Tage aufbewahrt. Die globale Grenze bleibt auch beim Löschen/Neuanlegen einer Sitzung bestehen und überlebt einen Prozessneustart. Die vorhandene HTTP-Begrenzung ergänzt dies. Diese Limits sind Anfragegrenzen; eine harte Währungsgrenze wird damit nicht garantiert. Für mehrere Server ist eine gemeinsam abgestimmte Quotenlösung nötig.

„Zeig mir die Stelle“ und die acht Tourhinweise verwenden ausschließlich feste Ziele der App. Boosty scrollt, hebt Felder hervor und bewegt seine erklärende Karte mit Zeiger. Er trägt nichts ein, bestätigt keine Angaben, exportiert oder versendet nichts und erteilt keine Adminrechte. Die Begleitung kann geschlossen werden; reduzierte Bewegung wird berücksichtigt.

Offizielle Grundlagen: [Responses Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [API-Datenkontrollen](https://developers.openai.com/api/docs/guides/your-data).
