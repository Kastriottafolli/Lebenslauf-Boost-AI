# Boosty AI · Lebenslauf Boost AI

Bewerbungswerkstatt auf Deutsch, Englisch und Albanisch: geprüftes Profil → Stellenanzeige → KI-Anbieter → vollständige, editierbare Bewerbungsmappe. Boosty AI ist die vom Betreiber gewählte Produktmarke. Betreiber ist **Kastriot Tafolli**, verbunden mit **[www.tafolli.net](https://www.tafolli.net)** und **info@tafolli.net**. Die gekaufte App-Domain ist **[tafolliboost.com](https://tafolliboost.com)**.

## Was funktioniert

- PDF/DOCX/TXT importieren, Kontaktdaten und erkannte Abschnitte prüfen. Originaltext und Profil bleiben editierbar.
- Fotos/Scans lokal mit Tesseract erkennen; deutsches, englisches und albanisches Sprachmodell liegen im Projekt. Kein OCR-Dienst erhält deine Bilder.
- Öffentliche HTTPS-Stellenlinks serverseitig importieren: bevorzugt `JobPosting`, sonst HTML. Private IPs, unzulässige Redirects und große Antworten werden blockiert. Für gesperrte Portale gibt es den Text-Eingang.
- OpenAI, Anthropic Claude, Google Gemini, xAI Grok und Microsoft Azure OpenAI: eigene API-Keys, Modell-/Deployment-Feld, Links zur Key-Erstellung und kostenpflichtiger Zugriffstest. Kein generischer Copilot-Key.
- Lebenslauf, Anschreiben, Motivationsschreiben und E-Mail gemeinsam erstellen. Dokumente separat bearbeiten und mit vollständigem Quellkontext nachbearbeiten.
- Begrenzte Dokumentvorschau mit eigenem Scrollbereich, direkt erreichbare Exportleiste und mobile Umschaltung zwischen Text und Vorschau. Sichtbare Keyword-Abdeckung mit gefundenen und fehlenden Begriffen; keine Einstellungschance.
- Boosty als Logo, animierte Begleitung und Hilfe; Erstellung zeigt vier bestätigte Phasen mit Tipps statt einer erfundenen Zeitprognose.
- Zwei KI-Anbieter vergleichen und einen Entwurf selbst auswählen. Kein behaupteter KI-Gewinner aus einer Keyword-Zahl.
- Sechs PDF-/Word-Designs, optionales Foto nur im Lebenslauf, komplette Mappe als ZIP. E-Mail kopieren oder als `mailto:`-Entwurf öffnen; kein automatischer Versand.
- Konto mit Passwort und einmaligem Wiederherstellungscode; Bewerbungen speichern, Status und Notizen pflegen, Projekte laden/löschen, Konto löschen.
- Ohne Konto: Projektdatei selbst herunterladen und wieder öffnen. Keys und Fotos sind nicht Teil dieser Projektdatei.
- Installierbare PWA, DE-/EN-/SQ-Ratgeber, responsive Oberfläche, Tastaturbedienung und reduzierte Bewegung.
- Capacitor-Projekte für Android/iOS mit Kamera, lokalem OCR, Datei-/Share-Export und Deep Links. Android empfängt außerdem geteilte HTTPS-Stellenlinks.

## Lokal starten

Node 22+ und Python 3.12+ werden benötigt. Es sind keine KI-Schlüssel nötig, um die Demo zu prüfen.

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

Der Browserbetrieb bietet Import, OCR, Demo, KI mit eigenem Key, Bearbeitung, PDF/Word/ZIP und lokale Projektdateien. Konten und Stellenlink-Import benötigen den Python-Server. API-Zugriff im Browser hängt auch von den CORS-Regeln des Anbieters ab; Azure vorzugsweise im Serverbetrieb nutzen.

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

`static/providers.json` ist die zentrale, am 05.10.2026 anhand offizieller Dokumentation geprüfte Anbieter-/Modellliste. Das Modellfeld erlaubt zukünftige Modelle und individuelle Azure-Deployments. Adapter verwenden OpenAI/xAI/Azure Responses, Anthropic Messages und Gemini `generateContent`.

API-Keys bleiben im Arbeitsspeicher; Server-Requests speichern sie nicht. Profile und Stellenanzeigen gehen bei KI-Nutzung an den gewählten Anbieter. `store:false` bei Responses ersetzt keine Datenschutzvereinbarung und bedeutet nicht automatisch Zero Data Retention. Gemini-Nutzung in Europa setzt gemäß Anbieterbedingungen ein Paid-Services-Projekt voraus. API-Abrechnung ist vom Chat-Abonnement getrennt.

Der Demo-Modus ist ausdrücklich regelbasiert. Er kopiert keine fehlenden Anforderungen als Kenntnisse. KI-Ausgaben müssen weiterhin geprüft werden: Promptregeln und Prüfhinweise sind keine mathematische Garantie gegen falsche Aussagen. Keyword-Abdeckung ist keine Einstellungswahrscheinlichkeit.

## Speicherung und Zugriff

Sitzungen benötigen zusätzlich zur ID einen `X-Session-Token`; dieser wird nicht in localStorage geschrieben. Kontozugriff läuft über ein ablaufendes HttpOnly-Cookie bzw. einen Bearer-Token im Arbeitsspeicher für mobile Clients. Passwörter verwenden scrypt, Login-/Recovery-Tokens werden gehasht. Kein E-Mail-Verifikationsdienst ist eingerichtet: Nutzer bewahren den einmalig angezeigten Recovery-Code selbst auf.

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

API-Tests laufen offline mit synthetischen Daten und gemockten KI-Antworten. Sie decken Besitzschutz, Konten/Recovery, Projektdaten, Upload-Grenzen, URL-Schutz, fehlerhafte Anbieterantworten und vollständigen Refinement-Kontext ab. Browser-Tests prüfen Adapter, faktentreue Demo sowie echte PDF/Word/ZIP-Dateien.

## Vor einem öffentlichen Start

[Release-Status und offene externe Schritte](docs/product/RELEASE.md) · [Marke, SEO und Launch](docs/product/LAUNCH.md) · [Technik und Datenschutzgrenzen](docs/product/ARCHITECTURE.md)

Domainkauf, Betreiberanschrift, Datenschutzerklärung für den tatsächlichen Hostingbetrieb, Live-KI-Tests mit eigenen Keys, mobile Builds/Signierung und Store-Einreichung sind noch erforderlich. Es gibt kein eingebautes Bezahlsystem; die erste Version setzt auf eigene API-Keys.

Die ausdrücklich gewählte Demo erstellt Dokumente lokal auch im Serverbetrieb. Nach dem ersten vollständigen Laden kann die gecachte PWA dafür genutzt werden; KI, Konten und Stellenimport benötigen eine Verbindung. OCR- und PDF-Worker müssen für Offline-Nutzung bereits geladen worden sein.

## Betreiber und dauerhafte Konten

Die lokale Konfiguration aus `.env.example` verwendet `data/tafolli.db`. Initialisieren und eine geprüfte Sicherung erstellen: `python -m backend.manage_database init` bzw. `python -m backend.manage_database backup`. Registrierung und gespeicherte Bewerbungen bleiben nach einem Serverneustart erhalten. Der Prüflauf testet dies mit zwei unabhängigen Prozessen.

Für die Veröffentlichung auf tafolliboost.com sind `.env.production.example`, `compose.production.yml` und `deploy/Caddyfile` vorbereitet. Die Vorlage verwendet `https://tafolliboost.com`; `www.tafolliboost.com` wird auf diese Adresse weitergeleitet. Beide DNS-Namen müssen auf den Server zeigen. Keine DNS-Änderung wurde durchgeführt. [Betreiber, Datenbank und Hosting](docs/product/TAFOLLI-HOSTING.md).

## Boosty AI · Admin und Hilfe

Die Marke ist Boosty AI. Das Maskottchen führt durch die Bewerbung und beantwortet Bedienungsfragen ohne API-Key; freie KI-Fragen benötigen Zustimmung und einen eigenen Anbieter-Key.

Unter `/admin` und über **Admin** in der App stehen separate MFA-Anmeldung, Konten, Nutzungsverlauf, Tagesstatistiken, gespeicherte Inhalte und Datenbankstatus bereit. Keine öffentliche Vergabe von Adminrechten und kein Standardpasswort. Einrichtung und Schutzgrenzen: [ADMIN.md](docs/product/ADMIN.md).

```sh
python -m backend.manage_admin --email DEINE-ADMIN-EMAIL
```

Die private Datei mit einmaligem Setup-Code bleibt außerhalb von Git und Webauslieferung. Auf dem Produktionsserver getrennt provisionieren. Passwort-Hashes, Tokens und Keys erscheinen nicht in den Datenansichten. Statistik zählt Seitenaufrufe/Sitzungen; keine exakte Zahl eindeutiger Besucher.

## Betreiberrechtstexte und Boosty-KI

Impressum und Datenschutzerklärung unter `/impressum/` und `/datenschutz/` sind dauerhaft verlinkt. Offene Betreiber-/Hostingangaben bleiben sichtbar als Entwurf: [Rechtstext-Vorbereitung](docs/product/LEGAL-READINESS.md). Der öffentliche GitHub-Link wurde entfernt; das Repository wird dadurch nicht privat.

Boosty bewegt sich mit Hinweis und Zeiger zu festen Bedienfeldern. Ein eigener serverseitiger OpenAI-Key kann ausschließlich die Software-Themenerkennung versorgen: [Sichere Einrichtung](docs/product/BOOSTY-SETUP.md). API-Key nicht im Chat teilen. [Token- und Kostenbeispiele](docs/product/AI-COSTS.md).
