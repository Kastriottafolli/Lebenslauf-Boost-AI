# tafolliboost.com · Bewerbung mit OpenAI

Bewerbungswerkstatt auf Deutsch, Englisch und Albanisch mit Pflichtkonto und zentral bereitgestellter OpenAI-KI. Boosty ist das Maskottchen und der Softwareassistent. Betreiber: **Kastriot Tafolli**, **info@tafolli.net**, **[www.tafolli.net](https://www.tafolli.net)**.

**Aktueller Betriebsmodus und Einrichtung:** [Zentrale OpenAI-KI, Pflichtkonto, Kostenlimits und Social-Login](docs/product/HOSTED-OPENAI.md). Die aktuelle Oberfläche bietet keine Gast- oder Nutzer-Key-Funktion. Frühere Anbieteradapter bleiben als technische Kompatibilität im Quellcode erhalten.


## Was funktioniert

- PDF/DOCX/TXT importieren, Kontaktdaten und erkannte Abschnitte prüfen. Originaltext und Profil bleiben editierbar.
- Fotos/Scans lokal mit Tesseract erkennen; deutsches, englisches und albanisches Sprachmodell liegen im Projekt. Kein OCR-Dienst erhält deine Bilder.
- Öffentliche HTTPS-Stellenlinks serverseitig importieren: bevorzugt `JobPosting`, sonst HTML. Private IPs, unzulässige Redirects und große Antworten werden blockiert. Für gesperrte Portale gibt es den Text-Eingang.
- Zentraler OpenAI-Zugang auf dem Server, ohne Nutzer-API-Key. Tageskontingente und Token-/Kostenzähler. Google, Apple, Facebook und X als konfigurierte Social-Login-Optionen vorbereitet.
- Lebenslauf, Anschreiben, Motivationsschreiben und E-Mail gemeinsam erstellen. Dokumente separat bearbeiten und mit vollständigem Quellkontext nachbearbeiten.
- Begrenzte Dokumentvorschau mit eigenem Scrollbereich, direkt erreichbare Exportleiste und mobile Umschaltung zwischen Text und Vorschau. Sichtbare Keyword-Abdeckung mit gefundenen und fehlenden Begriffen; keine Einstellungschance.
- Boosty als Logo, animierte Begleitung und Hilfe; Erstellung zeigt vier bestätigte Phasen mit Tipps statt einer erfundenen Zeitprognose.
- Sechs PDF-/Word-Designs, optionales Foto nur im Lebenslauf, komplette Mappe als ZIP. E-Mail kopieren oder als `mailto:`-Entwurf öffnen; kein automatischer Versand.
- Konto mit E-Mail-Bestätigung, Passwort-Zurücksetzen per E-Mail, bearbeitbarem Profil und eigenen Unterlagen; Bewerbungen speichern, Status und Notizen pflegen, Daten exportieren und geschützt löschen.
- Drei kostenlose Bewerbungsmappen pro Kalenderwoche (Europe/Berlin), dauerhafte Kaufcredits und vorbereitete Einzelkäufe (1,99 EUR / zehn für 9,99 EUR); Zahlungen erst nach Händleranbindung verfügbar.
- Erklärvideo in DE/EN/SQ mit KI-Sprecherstimme, eigener Musik, Untertiteln und nativen Videosteuerungen.
- Angemeldete Nutzer können Projektdateien herunterladen und wieder öffnen. Keys und Fotos sind nicht Teil dieser Projektdatei.
- Installierbare PWA, DE-/EN-/SQ-Ratgeber, responsive Oberfläche, Tastaturbedienung und reduzierte Bewegung.
- Capacitor-Projekte für Android/iOS mit Kamera, lokalem OCR, Datei-/Share-Export und Deep Links. Android empfängt außerdem geteilte HTTPS-Stellenlinks.

## Lokal starten

Node 22+ und Python 3.12+ werden benötigt. Für Build und Offline-Tests sind keine KI-Schlüssel nötig. Kontoaktivierung benötigt einen echten Mailtransport; die zentrale Dokumenterstellung benötigt einen privaten OpenAI-Server-Key.

```sh
npm ci --ignore-scripts
npm run build
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn backend.main:app --reload
```

Öffne `http://127.0.0.1:8000`. Die Server-Anwendung verwendet `frontend/build`; GitHub Pages verwendet `_site`. Nach Änderungen an Frontend oder Branding erneut `npm run build` ausführen.

### Browser / GitHub Pages

```sh
npm run build
python3 -m http.server 8080 --directory _site
```

Der statische Build liefert die Oberfläche und benötigt für Konten, zentrale KI und Stellenlink-Import den Python-Server. GitHub Pages ist mit der Produktions-API verbunden; ein selbst gebauter statischer Vorschau- oder Mobile-Build benötigt dafür eine konfigurierte `PUBLIC_API_BASE`. Anbieter-Keys gehören ausschließlich auf den Server.

Optional kann die Browser-/Mobile-Version auf einen eigenen HTTPS-Server zeigen:

```sh
PUBLIC_API_BASE=https://api.example.com npm run build
```

Diesen Ursprung und die Web-/Capacitor-Ursprünge in `ALLOWED_ORIGINS` freigeben. Nur öffentliche API-Basisadressen dürfen in den Build; niemals Secrets.

### Docker

```sh
cp .env.example .env
# Betreiber, gekaufte Domain, erlaubte Hosts/Ursprünge und sichere Cookies konfigurieren.
docker compose up --build -d
```

Die App bindet lokal auf Port 8000; für öffentlichen Betrieb HTTPS-Reverse-Proxy verwenden. Daten liegen im Docker-Volume. Ein Worker ist absichtlich voreingestellt: die eingebaute Anfragelimitierung gilt pro Prozess. Mehrere Worker benötigen gemeinsame Limits am Gateway.

## Modelle und Datenschutz

Der aktuelle Betriebsmodus nutzt zentral bereitgestellte OpenAI-Modelle; Nutzer wählen keinen Anbieter und geben keine API-Keys ein. Betreiber-Keys liegen in einer privaten Serverumgebung außerhalb von Git und Browserbuild. Profile und Stellenanzeigen gehen nach ausdrücklicher Freigabe an OpenAI. `store:false` bei Responses ersetzt keine Datenschutzvereinbarung und bedeutet nicht automatisch Zero Data Retention. API-Abrechnung ist vom Chat-Abonnement getrennt.

`static/providers.json` und die früheren OpenAI/xAI/Azure-, Anthropic- und Gemini-Adapter bleiben für technische Kompatibilität erhalten. Sie sind keine aktiv angebotene Anbieterwahl. KI-Ausgaben müssen weiterhin geprüft werden: Promptregeln und Prüfhinweise sind keine mathematische Garantie gegen falsche Aussagen. Keyword-Abdeckung ist keine Einstellungswahrscheinlichkeit.

## Speicherung und Zugriff

Sitzungen benötigen zusätzlich zur ID einen `X-Session-Token`; dieser wird nicht in localStorage geschrieben. Kontozugriff läuft über ein ablaufendes HttpOnly-Cookie bzw. einen Bearer-Token im Arbeitsspeicher für mobile Clients. Passwörter verwenden scrypt; Login-, Bestätigungs- und Zurücksetzungstokens werden gehasht. Neue E-Mail-Konten werden erst nach Bestätigung aktiviert. Passwort-Zurücksetzen erfolgt über einen zeitlich begrenzten Einmallink per E-Mail; die frühere Recovery-Code-Anmeldung ist deaktiviert. Temporäre Mailnutzlasten werden in der Outbox verschlüsselt und nach Zustellung verworfen.

Anonyme Upload-Sitzungen werden beim Serverstart und stündlich nach `RETENTION_DAYS` bereinigt. Abgelaufene Login-Tokens werden ebenfalls entfernt; Konten und gespeicherte Bewerbungen bleiben erhalten. Bei Bedarf manuell ausführen:

```sh
.venv/bin/python -m backend.cleanup
```

Kontobewerbungen bleiben bis zur ausdrücklichen Löschung. Exportierte Dateien und externe Backups bleiben in der Verantwortung des Nutzers. Betriebssystem-/Datenbankverschlüsselung und Backup-Aufbewahrung müssen beim Hosting eingerichtet werden.

### Bestehende Datenbank

Vor dem ersten Start eine Sicherung von `data/app.db` erstellen. Die idempotente Initialisierung ergänzt Besitzfelder und kopiert historische Generationen in `generations_v2`, ohne die alte Tabelle zu löschen. Alte, bisher ungeschützte Sitzungen werden nicht automatisch einem Nutzer zugeordnet; ihr Wiederzugriff erfordert eine administrativ geprüfte Zuordnung. `docs/schema.sql` beschreibt den früheren Stand; das aktuelle Schema steht in `backend/models.py`.

## Android und iOS

```sh
npm run mobile:sync
npm run mobile:android
npm run mobile:ios
```

Die nativen Quellen liegen in `android/` und `ios/`. Zum Kompilieren werden Android Studio/JDK/SDK bzw. vollständiges Xcode benötigt. Bundle-ID, Signing, Store-Konten und App-Icons vor Veröffentlichung prüfen. Native Funktionen wurden in dieser Umgebung nicht auf echten Geräten ausgeführt. Siehe [Mobile-Release](docs/product/MOBILE.md).

## Prüfen

```sh
npm test
npm run build
.venv/bin/python -m pytest backend/tests -q
ruff check backend
```

API-Tests laufen offline mit synthetischen Daten und gemockten KI-Antworten. Sie decken Besitzschutz, Kontobestätigung und Passwort-Zurücksetzen, Wochencredits, Projektdaten, Upload-Grenzen, URL-Schutz, fehlerhafte Anbieterantworten und vollständigen Refinement-Kontext ab. Frontend-Tests prüfen unter anderem Kontoflüsse, Guthabenanzeige, Adapter und echte PDF/Word/ZIP-Dateien. Echte Mailzustellung und Produktionskonten werden zusätzlich mit eigenen Testkonten geprüft.

## Vor einem öffentlichen Start

[Release-Status und offene externe Schritte](docs/product/RELEASE.md) · [Marke, SEO und Launch](docs/product/LAUNCH.md) · [Technik und Datenschutzgrenzen](docs/product/ARCHITECTURE.md)

tafolliboost.com läuft mit HTTPS auf DreamHost und zentral bereitgestellter OpenAI-KI. Mailbestätigung, Kontoverwaltung und Zahlungslogik sind implementiert. Extern offen bleiben freigeschaltete Social-Login-Apps, Zahlungshändlerkonfiguration, rechtliche Betreiber-/Vertragsprüfung und signierte Store-Veröffentlichungen.

Die PWA kann bereits geladene Oberflächen und lokale Bearbeitungs-/Exportfunktionen cachen. Zentrale KI, Konten, gespeicherte Bewerbungen und Stellenimport benötigen eine Verbindung. OCR- und PDF-Worker müssen für lokale Nutzung bereits geladen worden sein; ein Gast- oder Demoeditor wird im aktuellen Betriebsmodus nicht angeboten.

## Betreiber und dauerhafte Konten

Die lokale Konfiguration aus `.env.example` verwendet `data/tafolli.db`. Initialisieren und eine geprüfte Sicherung erstellen: `python -m backend.manage_database init` bzw. `python -m backend.manage_database backup`. Registrierung und gespeicherte Bewerbungen bleiben nach einem Serverneustart erhalten. Der Prüflauf testet dies mit zwei unabhängigen Prozessen.

Für die Veröffentlichung auf tafolliboost.com sind `.env.production.example`, `compose.production.yml` und `deploy/Caddyfile` vorbereitet. Die Vorlage verwendet `https://tafolliboost.com`; `www.tafolliboost.com` wird auf diese Adresse weitergeleitet. Beide DNS-Namen müssen auf den Server zeigen. Die Produktionsdomain ist verbunden; tafolli.net bleibt die bestehende Betreiberhomepage. [Betreiber, Datenbank und Hosting](docs/product/TAFOLLI-HOSTING.md).

## Boosty AI · Admin und Hilfe

Die Webseite heißt tafolliboost.com. Boosty ist das Maskottchen und führt durch die Bewerbung. Seine Softwarehilfe nutzt den zentralen serverseitigen OpenAI-Zugang und lokal verfügbare Bedienhinweise.

Unter `/admin` und über **Admin** in der App stehen separate MFA-Anmeldung, Konten, Nutzungsverlauf, Tagesstatistiken, gespeicherte Inhalte und Datenbankstatus bereit. Keine öffentliche Vergabe von Adminrechten und kein Standardpasswort. Einrichtung und Schutzgrenzen: [ADMIN.md](docs/product/ADMIN.md).

```sh
python -m backend.manage_admin --email DEINE-ADMIN-EMAIL
```

Die private Datei mit einmaligem Setup-Code bleibt außerhalb von Git und Webauslieferung. Auf dem Produktionsserver getrennt provisionieren. Passwort-Hashes, Tokens und Keys erscheinen nicht in den Datenansichten. Statistik zählt Seitenaufrufe/Sitzungen; keine exakte Zahl eindeutiger Besucher.

## Betreiberrechtstexte und Boosty-KI

Impressum und Datenschutzerklärung unter `/impressum/` und `/datenschutz/` sind dauerhaft verlinkt. Der öffentliche Entwurfshinweis wurde entfernt; die interne fachliche Prüfung bleibt dokumentiert: [Rechtstext-Vorbereitung](docs/product/LEGAL-READINESS.md). Der öffentliche GitHub-Link wurde entfernt; das Repository wird dadurch nicht privat.

Boosty bewegt sich mit Hinweis und Zeiger zu festen Bedienfeldern. Seine aktuelle Softwarehilfe verwendet denselben privaten OpenAI-Serverzugang wie die Dokumenterstellung: [Aktueller Betriebsmodus](docs/product/HOSTED-OPENAI.md). Die frühere separate Boosty-Konfiguration bleibt in [BOOSTY-SETUP.md](docs/product/BOOSTY-SETUP.md) dokumentiert. API-Key nicht im Chat teilen. [Token- und Kostenbeispiele](docs/product/AI-COSTS.md).

Aktuelle Betriebsdokumente: [Konto-E-Mails](docs/deploy/ACCOUNT-MAIL.md), [Wochencredits und Zahlungslogik](docs/product/BILLING.md), [Traffic](docs/product/TRAFFIC.md), [Backups](docs/deploy/BACKUPS.md).
