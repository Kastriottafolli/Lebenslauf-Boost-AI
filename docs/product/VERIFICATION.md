# Prüfnachweis · 05.10.2026

## Automatisiert

- Backend: 53 Tests für API, Sitzungsbesitz, Konten/Recovery, Projektspeicherung, Dateigrenzen, Body-Limit ohne Content-Length, HTTPS-Stellenimport, Anbieterfehler und vollständigen Revisionskontext. Ein zusätzlicher Test registriert und speichert in einem Prozess und prüft Anmeldung/Projektzugriff nach einem echten Prozessneustart einschließlich einer geprüften SQLite-Sicherung. Retention-Test: abgelaufene anonyme Daten und Login-Tokens entfernt, Konten/Bewerbungen erhalten.
- Frontend: 20 Tests für Demo-Fakten, Anbieter-Verträge, Import-/Exportgrenzen, sechs PDF-Layouts mit Unicode, lesbare Word-Dateien und ZIP-Inhalte.
- `ruff check backend` und `git diff --check`: erfolgreich.
- `npm run build` und `npx cap sync`: erfolgreich für Browser, Server, Android und iOS.
- Apple Info.plist, PrivacyInfo.xcprivacy und project.pbxproj: `plutil -lint` erfolgreich.
- Produktions-Konfiguration: GitHub-CI prüft Compose und Caddy syntaktisch, ohne öffentlichen Serverstart oder DNS-Änderung.
- `npm audit --omit=dev` und `pip-audit -r requirements.txt` einschließlich aufgelöster Python-Abhängigkeiten: keine bekannten gemeldeten Schwachstellen. Dies ist keine Garantie, dass keine unbekannten Schwachstellen vorhanden sind.

## Admin, Boosty und Updates

- Admin: öffentliche Registrierung und normale Login-Tokens können keine Adminrechte vergeben; CSRF/Origin-Regeln, native CORS-Preflights, MFA inklusive RFC-6238-Testvektor, Replay-Schutz, Setup-Ablauf, 15-Minuten-Sitzung, Widerruf und serverseitige Wiederherstellung geprüft.
- Admin-Konto, MFA-Replay-Zustand und Admin-Sitzung auch nach einem echten Prozessneustart verifiziert.
- Auditiert: einzelne Nutzerdaten-/Bewerbungszugriffe. API-Ansichten enthalten keine Passwort-Hashes, Schlüssel oder Tokens. E-Mail-Suche mit Sonderzeichen und Query-Grenzen geprüft.
- Verstärkte scrypt-Parameter mit kompatibler Aktualisierung alter Hashes, persistente Limits je Identität, Statistik-Retention und Entkopplung bei Kontolöschung geprüft.
- Boosty: Bedienungsantworten in DE/EN/SQ, Tour über alle vier Schritte, KI nur mit Zustimmung/Session-Besitz/eigenem Key. Mock-Anfrage enthält weder Lebenslauf noch API-Key im Prompt.
- Browser: Anmeldung eines ausschließlich synthetischen Admin-Testkontos in einer getrennten Datenbank, Dashboard, Nutzerliste, Bewerbungsinhalt, Admin-Protokoll und erfolgreiche Abmeldung geprüft. Keine Aktivierung oder Passwortvergabe für das echte Betreiberkonto durch den Agenten.
- Versionen von HTML, App/CSS und Service-Worker stimmen überein; alte Cache-Dateien werden abgelöst. Admin/API werden nicht im Service-Worker gecacht.
- Mobile Boosty-Frage zur Speicherung ohne Key beantwortet, Admin-Button bei 429 px sichtbar. Keine Browser-Konsolenfehler.

## Im Browser mit synthetischen Daten

Beispielprofil → Fakten bestätigen → Stellenbeschreibung → ausdrückliche Demo → vier editierbare Dokumente. DE/EN/SQ-Oberfläche sowie englische und albanische Demo-Vorlagen geprüft; die Demo übersetzt den ursprünglichen Lebenslauf nicht automatisch. Die neueste Demo läuft auch im Serverbetrieb lokal und sendet keinen KI-Aufruf.

Ein synthetischer Bildscan wurde lokal mit Tesseract erkannt; Name, E-Mail und Text erschienen zur manuellen Prüfung. Keine Fehlermeldungen in der Browserkonsole.

PDF und Word wurden über die Oberfläche heruntergeladen und mit pypdf/python-docx erneut gelesen. Der PDF-Lebenslauf enthielt unter anderem Name, React, Jahreszahlen und die ursprüngliche 25-%-Angabe. Die ZIP-Datei wurde geöffnet: drei Dokumente, email.txt und README.txt, ohne beschädigte Einträge.

Eine mobile Breite wurde angefordert und die tatsächlich gemessene Browserbreite von 429 px kontrolliert: kein horizontaler Überlauf. Desktop-Dokumentvorschau geprüft. Diese Kontrolle ersetzt keinen Test auf Android-/iOS-Geräten.

## Nicht verifiziert

- Kostenpflichtige Live-Anfragen: keine Benutzer-API-Keys eingesetzt. Anbieter-Verträge sind gemockt; Konto-/Region-/Modellzugriff und Browser-CORS bleiben beim Anbieter zu testen.
- Android/iOS: native Quellen synchronisiert, aber keine APK/AAB/IPA erstellt. JDK/Android SDK bzw. vollständiges Xcode fehlen.
- Docker-Image: Konfiguration erstellt, Docker ist hier nicht verfügbar; Image-Build nicht durchgeführt.
- Endor Dependency Reviewer: Skill gelesen, Endor-MCP/CLI nicht verfügbar. Zusätzliche Endor-Risiko-, Lizenz- und Maintenance-Bewertung **UNKNOWN**, nicht bestanden behauptet. npm/pip-Audits sind davon unabhängige Prüfungen.
- Öffentliche Veröffentlichung, Markenfreigabe, SMTP, Checkout und Store-Freigabe: nicht erfolgt. www.tafolli.net und info@tafolli.net sind als Betreiberverbindung hinterlegt; keine bestehende Website ersetzt und kein DNS-Eintrag verändert.

Die verbleibenden Betriebs- und Ausbaupunkte stehen in RELEASE.md und MOBILE.md. Der Stand ist eine prüfbare Beta.

## Schritt 4, Texte und Albanisch

- Insgesamt 73 automatische Tests bestanden. Zusätzliche Prüfungen: DE/EN/SQ-Briefe verwenden tatsächliche CV-Belege, Aufgaben aus der Anzeige und persönliche Motivation; keine fehlenden Qualifikationen erfunden. Kurze Briefe werden als Prüfhinweis markiert. Lebenslauf bleibt in der Demo in seiner Originalsprache.
- In Google Chrome: synthetischer Lebenslauf mit 120 Projekten; Vorschau 446 px hoch bei 6632 px Inhalt. Scrollen innerhalb der Vorschau bewegt nicht die äußere Seite. Exportleiste steht oberhalb der Vorschau. Sichtbare 75 % entsprechen 12 von 16 Stichwörtern. Der ursprüngliche Nutzertab wurde nicht neu geladen.
- Chrome-Downloads erneut gelesen: Word enthält den ersten und letzten Projektabschnitt; PDF hat sechs Seiten und enthält Alex Beispiel sowie Projekt 120.
- Mobile Prüfung zusätzlich im In-App-Browser bei tatsächlich gemessenen 390 px: kein horizontaler Überlauf, nur Vorschau oder Texteditor sichtbar. Umschaltung funktioniert, Editor auf 380 px begrenzt. Chromes angeforderte Breite blieb 1475 px und wurde deshalb nicht als bestandener mobiler Chrome-Test gewertet.
- Ladeoberfläche mit getrenntem Mock-Server: 25 % nach geprüften Eingaben; weitere Phasen nach Antwort, Dokumentprüfung und Abschluss. Allgemeine Importe/Exporte zeigen eine unbestimmte Ladeanzeige, OCR seinen tatsächlich gemeldeten Fortschritt. Keine Live-KI genutzt.
- Albanische Oberfläche, Dokumentvorlagen, Hilfe, Tour, Ratgeber, API-Sprachwerte und Legacy-Prompts geprüft. Eigenes lokales Tesseract-sqi-Modell verarbeitet einen synthetischen Scan; Name und berufliche Inhalte erkannt, E-Mail/Einzelwörter teilweise falsch. Manuelle OCR-Prüfung bleibt erforderlich. Automatischer Chrome-Dateiupload scheiterte an der nicht aktivierten Erweiterungsberechtigung für Datei-URLs; OCR separat lokal geprüft.
- Idempotente SQLite-Sprachmigration erhält bestehende Sitzungen, abhängige Daten und Indizes; vor der Umstellung wird eine nicht überschreibbare Sicherung mit Dateirechten 0600 erstellt. Migration an lokaler Preview-Datenbank abgeschlossen. Betreiber verwaltet Aufbewahrung und Löschung dieser personenbezogenen Backups.
- Boosty ersetzt das Pfeil-Logo auch in PWA- und nativen App-Icons. Capacitor-Quellen erneut synchronisiert; native Geräte-Builds weiterhin nicht verifiziert.

## Domain tafolliboost.com

Die Domain wurde laut Betreiber gekauft. App-Links, Branding, Produktions-Hosts und -Origins, Canonicals, Open-Graph-URL und Sitemap sind auf https://tafolliboost.com angepasst. Caddy leitet www.tafolliboost.com einschließlich Pfad/Query auf die Hauptadresse weiter. Betreiberwebsite und info@tafolli.net bleiben bestehen. Keine DNS-Einträge, GitHub-Pages-Domain oder öffentliche Server wurden verändert.

Domain-Prüfung: Server-HTML und Browser-Build liefern die neue Canonical-/Open-Graph-Adresse. Sitemap enthält Startseite und alle sechs DE/EN/SQ-Ratgeber; Footer-Links und robots.txt geprüft. 64 Tests, Ruff und Build/Capacitor-Sync bestanden. HTTPS-Ausstellung und Weiterleitung sind für den späteren Serverbetrieb vorbereitet, lokal nicht als öffentlich aktiv getestet.

## Rechtstexte und fokussierte Boosty-Hilfe

- 53 Backend- und 20 Frontend-Tests bestanden. Neue Tests prüfen Einwilligung/Sitzungsbesitz, getrennten Betreiber-Key ohne Dokumentzugriff, versteckte Schlüssel, feste Hilfethemen statt freier Modelltexte, manipulierte/unerwartete Modellantworten und persistente Sitzung-/Gesamtquoten. Kein echter OpenAI-Key und keine kostenpflichtige Anfrage verwendet.
- Öffentliches HTML enthält keinen Repository-Link. Boosty-SVG ist als Favicon mit Versionskennung eingebunden, auch im Adminbereich; Apple-Touch-Icon bleibt das Boosty-Rasterbild.
- Eigene Impressums-/Datenschutzseiten in der Server-App und im Browser-Build; Inhaltsverzeichnis, Rechte, Speicherfristen, notwendiger Browser-Speicher, optionale KI und separate Boosty-Fragen. Betreiberwerte HTML-escaped; fehlende Hosting-/Betreiberbestätigungen sichtbar als Entwurf, EN/SQ ausdrücklich Zusammenfassungen. Keine juristische Vollständigkeit ohne tatsächliche Betreiber-/Vertragsangaben behauptet.
- Begleitung im Browser: Frage zum Import → „Zeig mir die Stelle“ → automatisches Scrollen, begrenzte bewegliche Karte und Zeiger auf Upload-Feld. Nächster Hinweis zeigt auf Profilfelder; Schließen und Ablehnen eines Programmierauftrags geprüft. Persönliche Nutzertabs bleiben unverändert.
- Token-/Preisbeispiele aus aktuellen offiziellen OpenAI-Standardtarifen berechnet und als Annahmen, nicht als gemessene Live-Nutzung gekennzeichnet.

## HTTPS-Stellenimport (05.10.2026)

- Der vom Betreiber genannte öffentliche StudySmarter-Link zum F&B Manager bei Parkhotel Flora Schluchsee scheiterte am fehlenden lokalen Python-Zertifikatsspeicher (`SSLCertVerificationError`). Der Importer ergänzt jetzt das explizit versionierte Certifi-Zertifikatsbundle zu den vorhandenen Trust Roots; Zertifikats-/Hostnameprüfung und DNS-Pinning bleiben aktiv.
- Derselbe Link anschließend direkt und über „Link einlesen“ im In-App-Browser erfolgreich: Position und Arbeitgeber erkannt, 5.404 Zeichen Originalbeschreibung ohne Kürzung übernommen. Keine Bewerbung erstellt oder versendet und keine KI-Anfrage durchgeführt. Drittportale mit Login oder Importsperren können weiterhin eine manuell eingefügte Beschreibung erfordern.
- 26 gezielte Backend-Tests bestanden, einschließlich vier neuer Transport-Regressionen: Betrieb ohne System-Trust-Roots, Prüfung des ursprünglichen Hostnamens am gepinnten Ziel, geschlossene Sockets bei TLS-Fehlern, kein unsicherer Retry bei ungültigem Zertifikat und keine interne Zieladresse über Weiterleitungen. Ruff und Diff-Prüfung bestanden.

## Unmittelbare Designvorschau (05.10.2026)

- Designwahl rendert jetzt unmittelbar die Vorschau: alle sechs Stile mit gemessenen Farb-/Schrift-/Ausrichtungswechseln im In-App-Browser geprüft. Keine KI-Neuerstellung nötig. Auf 390 px breitem Bildschirm wird die Textbearbeitung beim Designwechsel zur sichtbaren Vorschau; 390 px Seitenbreite, kein horizontaler Überlauf.
- Gemeinsame Palette und lokal bereitgestellte Noto Sans/Noto Serif in regulär/fett; PDF bettet die Fonts ein. Sechs PDF-/Word-Exporte mit 120 Projekten programmatisch erzeugt und erneut gelesen: Unicode und letzter Projekteindruck bleiben erhalten. Die sechs Browser-PDFs haben jeweils vier Seiten; erste PDF-Seiten gerendert, Classic/Sapphire visuell geprüft. Der IAB-Download-Ereignistest lieferte keinen zugänglichen Dateipfad; diese Dateiprüfungen beruhen ausdrücklich auf dem aktuellen Exportmodul.
- Langer Test-CV in der Oberfläche: 401 px Vorschauhöhe bei 5.814 px Inhalt; mobil 378 px. Vorschau bleibt intern scrollbar. Änderungen im Text werden als Textknoten dargestellt, keine Interpretation von HTML.
- Gewählte Designkennung wird mit Projektdateien/Kontobewerbungen gespeichert und bei alten Projekten auf Modern zurückgesetzt. Konto-Tests prüfen Speicherung und Wechsel von Classic zu Sapphire sowie Besitzrechte.
- 58 Backend- und 21 Frontend-Tests bestanden; nach der Änderung am Projektfeld erneut die betroffenen Backend-Tests bestanden. Ruff, Diff-Prüfung, Build und Capacitor-Sync bestanden. Keine Live-KI-Anfrage, öffentliche Veröffentlichung oder Änderung persönlicher Nutzertabs.

## Boosty-Neugestaltung und Kontoverlauf

Die neue 3D-Illustration, ihre CSS-Animationen, Startoptionen, Gesprächsblasen und automatische Kontospeicherung sind in [BOOSTY-REDESIGN.md](BOOSTY-REDESIGN.md) dokumentiert. Aktueller Prüfstand: 62 Backend- und 22 Frontendtests. Browserprüfung mit separater Testdatenbank: Entwurf → Generierung → Design → Abmeldung → erneuter Login → Wiederherstellung, zusätzlich mobile albanische Hilfe bei 390 × 844 Pixeln. Keine echte Betreiber-KI oder private Nutzerdaten eingesetzt.
