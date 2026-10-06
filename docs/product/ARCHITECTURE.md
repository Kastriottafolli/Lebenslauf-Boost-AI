# Architektur und Grenzen

## Drei Laufzeiten, ein Editor

`frontend/js/app.js` enthält die Oberfläche. `frontend/js/core/application.js` enthält Profilimport, Quellregeln und Validierung sowie den früheren lokalen Demo-Code. Der aktuelle Betriebsmodus verlangt ein Konto und verwendet zentrale OpenAI-Aufrufe auf dem Server. `static/providers.json` und frühere Anbieteradapter bleiben als technische Kompatibilität erhalten; ihre Request-/Response-Verträge werden weiterhin getestet.

- Server: FastAPI + SQLAlchemy/SQLite. Verifizierte Konten, Sitzungsbesitz, geschützte Bewerbungsspeicherung, HTTPS-Stellenimport, zentrale OpenAI-KI und Wochencredits.
- Browser: esbuild-Paket mit lokalem Dateiimport/OCR/Export und Konto-/KI-Zugriff auf die eigene API. Keine Nutzer-Key-Eingabe oder aktive BYOK-Oberfläche; kein unsicherer öffentlicher Proxy als CORS-Umgehung.
- Mobile: derselbe Browser-Build mit Capacitor. Ein eigener HTTPS-Server kann zur Buildzeit per `PUBLIC_API_BASE` gesetzt werden. Kamera, Filesystem, Share und App-Events werden nur nativ geladen.

Eine SQLite-Datenbank ist für einen einzelnen Pilotserver geeignet. PostgreSQL wird durch bedingte `connect_args` grundsätzlich ermöglicht; ein PostgreSQL-Treiber und echte Migrations-/Backup-Tests sind noch nicht eingerichtet. Nicht als verifiziertes PostgreSQL-Deployment behandeln.

## Fakten und KI

Das Profil ist bewusst ein Vorschlag aus Heuristiken, keine automatisch bestätigte Identität. Das Original bleibt vollständig erhalten. Änderungen am Profil heben die Bestätigung auf. Die KI erhält Original, bestätigte Korrekturen, gesamte Stellenbeschreibung und aktuelle Revision. Kein RAG-Ausschnitt ersetzt den vollständigen Quellkontext.

Neue Kennzahlen und Platzhalter werden angezeigt; dieser Check ist keine vollständige semantische Faktenprüfung. Jeder erzeugte Entwurf muss durch den Nutzer geprüft werden. Anbieterfehler und abgeschnittene Antworten erzeugen keine vermeintlich erfolgreichen Demo-Entwürfe.

## Sicherheitsgrenzen

- Session-ID allein reicht nicht. Besitz wird über einen separaten, gehashten Token geprüft.
- Konto: scrypt, zufällige ablaufende Login-Tokens, SameSite/HttpOnly-Cookie, ausdrückliche AGB-Annahme und E-Mail-Verifikation. Bestätigungs- und Passwort-Zurücksetzungslinks sind zeitlich begrenzt, gehasht und einmalig nutzbar. Passwortänderungen widerrufen vorhandene Anmeldungen. Kontolöschung verlangt aktuelle Anmeldung, Passwort und separate Bestätigung.
- Mail: verschlüsselte temporäre Outbox mit Retry/Lease und produktiv konfiguriertem HTTPS-Relay auf DreamHost Shared Hosting. HMAC, Zeitfenster, Replay-Schutz, fester Absender und TLS-Zertifikatsprüfung begrenzen den Relay-Zugriff. SMTP bleibt ein alternativer konfigurierbarer Transport.
- Betreiber-Keys liegen ausschließlich in der privaten Serverumgebung, nicht in Projekten, Logs, Git oder Browserbuild. Zentrale KI verlangt ein verifiziertes Konto und verwendet getrennte Konto-/Tageslimits, ein globales Kostenbudget und drei kostenlose Mappen pro Kalenderwoche. Kaufcredits und Zahlungslogik sind vorbereitet; echte Zahlungen bleiben bis zur Händleranbindung und Prüfung deaktiviert. Skalierung erfordert gemeinsame Limits.
- Dateiparser laufen in einem eigenen Prozess: 20 Sekunden Wandzeit, CPU-Limit, auf Linux 512 MB Adressraum, 10 MB Datei, 30 PDF-Seiten, 60.000 Textzeichen und 25 MB entpacktes DOCX.
- Stellenimport: nur HTTPS, öffentliche aufgelöste IPs, gepinnte Verbindung, erneute Prüfung pro Redirect, 2 MB HTML und 15 Sekunden Deadline. Keine Login-/Paywall-Umgehung. Eine JavaScript-gerenderte Anzeige kann einen manuellen Textimport benötigen.
- Server setzt Origin-Prüfung, Host-Allowlist, CSP, `no-store` für APIs und Prozess-Limits. Bei Proxy/Skalierung eine gemeinsame Limitierung einrichten; forwarded Header sind kein direkter Vertrauensnachweis.
- Service Worker speichert ausschließlich öffentliche Programmdateien. Keine API-Antworten, Profile, Bewerbungen oder Keys.
- Persönliche DB-/Backupdateien benötigen begrenzten Zugriff und dokumentierte Löschfristen. Die App implementiert keine eigene vollständige Datenbankverschlüsselung; Admin-Secrets und temporäre Mailnutzlasten sind separat verschlüsselt. Die eingerichteten täglichen Backups sind verschlüsselt, enthalten die benötigten passenden Schlüssel und werden 14 Tage aufbewahrt. Eine Sicherung auf demselben VPS schützt nicht vor vollständigem Serververlust; externe Sicherung bleibt offen.

## Anbieterquellen

- OpenAI: https://developers.openai.com/api/docs/guides/text
- Anthropic: https://platform.claude.com/docs/en/models/overview
- Gemini: https://ai.google.dev/api/generate-content
- Grok: https://docs.x.ai/developers/quickstart
- Azure: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses
- Copilot-Abgrenzung: https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/overview

Modellverfügbarkeit ist konto- und regionsabhängig. Lokale Vertragstests ersetzen keinen Live-Test beim jeweiligen Anbieter.
