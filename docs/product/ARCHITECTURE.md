# Architektur und Grenzen

## Drei Laufzeiten, ein Editor

`frontend/js/app.js` enthält die Oberfläche. `frontend/js/core/application.js` enthält Profilimport, Quellregeln, Demo-Mappe und Validierung. `static/providers.json` wird von JavaScript und Python gelesen. Die Anbieteradapter besitzen dieselben dokumentierten Request-/Response-Verträge, die in beiden Laufzeiten getestet werden.

- Server: FastAPI + SQLAlchemy/SQLite. Konto, Sitzungsbesitz, geschützte Bewerbungsspeicherung, HTTPS-Stellenimport und KI-Proxy.
- Browser: esbuild-Paket mit lokalem Dateiimport/OCR/Export und direkten BYOK-KI-Anfragen. Kein unsicherer öffentlicher Proxy als CORS-Umgehung.
- Mobile: derselbe Browser-Build mit Capacitor. Ein eigener HTTPS-Server kann zur Buildzeit per `PUBLIC_API_BASE` gesetzt werden. Kamera, Filesystem, Share und App-Events werden nur nativ geladen.

Eine SQLite-Datenbank ist für einen einzelnen Pilotserver geeignet. PostgreSQL wird durch bedingte `connect_args` grundsätzlich ermöglicht; ein PostgreSQL-Treiber und echte Migrations-/Backup-Tests sind noch nicht eingerichtet. Nicht als verifiziertes PostgreSQL-Deployment behandeln.

## Fakten und KI

Das Profil ist bewusst ein Vorschlag aus Heuristiken, keine automatisch bestätigte Identität. Das Original bleibt vollständig erhalten. Änderungen am Profil heben die Bestätigung auf. Die KI erhält Original, bestätigte Korrekturen, gesamte Stellenbeschreibung und aktuelle Revision. Kein RAG-Ausschnitt ersetzt den vollständigen Quellkontext.

Neue Kennzahlen und Platzhalter werden angezeigt; dieser Check ist keine vollständige semantische Faktenprüfung. Jeder erzeugte Entwurf muss durch den Nutzer geprüft werden. Anbieterfehler und abgeschnittene Antworten erzeugen keine vermeintlich erfolgreichen Demo-Entwürfe.

## Sicherheitsgrenzen

- Session-ID allein reicht nicht. Besitz wird über einen separaten, gehashten Token geprüft.
- Konto: scrypt, zufällige ablaufende Login-Tokens, SameSite/HttpOnly-Cookie, einmaliger Recovery-Code mit Rotation. E-Mail-Verifikation und SMTP sind nicht konfiguriert.
- Keys bleiben pro Anfrage, keine Speicherung in Projekten/Logs. Serverseitige Keys sind standardmäßig aus; bei Aktivierung ist eine Anmeldung nötig. Für bezahlten öffentlichen Betrieb zusätzlich Quoten/Billing am Gateway implementieren.
- Dateiparser laufen in einem eigenen Prozess: 20 Sekunden Wandzeit, CPU-Limit, auf Linux 512 MB Adressraum, 10 MB Datei, 30 PDF-Seiten, 60.000 Textzeichen und 25 MB entpacktes DOCX.
- Stellenimport: nur HTTPS, öffentliche aufgelöste IPs, gepinnte Verbindung, erneute Prüfung pro Redirect, 2 MB HTML und 15 Sekunden Deadline. Keine Login-/Paywall-Umgehung. Eine JavaScript-gerenderte Anzeige kann einen manuellen Textimport benötigen.
- Server setzt Origin-Prüfung, Host-Allowlist, CSP, `no-store` für APIs und Prozess-Limits. Bei Proxy/Skalierung eine gemeinsame Limitierung einrichten; forwarded Header sind kein direkter Vertrauensnachweis.
- Service Worker speichert ausschließlich öffentliche Programmdateien. Keine API-Antworten, Profile, Bewerbungen oder Keys.
- Persönliche DB-/Backupdateien benötigen beim Betreiber Verschlüsselung, begrenzten Zugriff und dokumentierte Löschfristen. Die App implementiert keine eigene Datenbankverschlüsselung.

## Anbieterquellen

- OpenAI: https://developers.openai.com/api/docs/guides/text
- Anthropic: https://platform.claude.com/docs/en/models/overview
- Gemini: https://ai.google.dev/api/generate-content
- Grok: https://docs.x.ai/developers/quickstart
- Azure: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses
- Copilot-Abgrenzung: https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/overview

Modellverfügbarkeit ist konto- und regionsabhängig. Lokale Vertragstests ersetzen keinen Live-Test beim jeweiligen Anbieter.
