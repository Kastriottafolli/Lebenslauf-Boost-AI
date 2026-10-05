# Prüfnachweis · 05.10.2026

## Automatisiert

- Backend: 40 Tests für API, Sitzungsbesitz, Konten/Recovery, Projektspeicherung, Dateigrenzen, Body-Limit ohne Content-Length, HTTPS-Stellenimport, Anbieterfehler und vollständigen Revisionskontext. Ein zusätzlicher Test registriert und speichert in einem Prozess und prüft Anmeldung/Projektzugriff nach einem echten Prozessneustart einschließlich einer geprüften SQLite-Sicherung. Retention-Test: abgelaufene anonyme Daten und Login-Tokens entfernt, Konten/Bewerbungen erhalten.
- Frontend: 15 Tests für Demo-Fakten, Anbieter-Verträge, Import-/Exportgrenzen, sechs PDF-Layouts mit Unicode, lesbare Word-Dateien und ZIP-Inhalte.
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
- Boosty: Bedienungsantworten in DE/EN, Tour über alle vier Schritte, KI nur mit Zustimmung/Session-Besitz/eigenem Key. Mock-Anfrage enthält weder Lebenslauf noch API-Key im Prompt.
- Browser: Anmeldung eines ausschließlich synthetischen Admin-Testkontos in einer getrennten Datenbank, Dashboard, Nutzerliste, Bewerbungsinhalt, Admin-Protokoll und erfolgreiche Abmeldung geprüft. Keine Aktivierung oder Passwortvergabe für das echte Betreiberkonto durch den Agenten.
- Versionen von HTML, App/CSS und Service-Worker stimmen überein; alte Cache-Dateien werden abgelöst. Admin/API werden nicht im Service-Worker gecacht.
- Mobile Boosty-Frage zur Speicherung ohne Key beantwortet, Admin-Button bei 429 px sichtbar. Keine Browser-Konsolenfehler.

## Im Browser mit synthetischen Daten

Beispielprofil → Fakten bestätigen → Stellenbeschreibung → ausdrückliche Demo → vier editierbare Dokumente. DE/EN-Oberfläche und englische Demo-Vorlagen geprüft; die Demo übersetzt den ursprünglichen Lebenslauf nicht automatisch. Die neueste Demo läuft auch im Serverbetrieb lokal und sendet keinen KI-Aufruf.

Ein synthetischer Bildscan wurde lokal mit Tesseract erkannt; Name, E-Mail und Text erschienen zur manuellen Prüfung. Keine Fehlermeldungen in der Browserkonsole.

PDF und Word wurden über die Oberfläche heruntergeladen und mit pypdf/python-docx erneut gelesen. Der PDF-Lebenslauf enthielt unter anderem Name, React, Jahreszahlen und die ursprüngliche 25-%-Angabe. Die ZIP-Datei wurde geöffnet: drei Dokumente, email.txt und README.txt, ohne beschädigte Einträge.

Eine mobile Breite wurde angefordert und die tatsächlich gemessene Browserbreite von 429 px kontrolliert: kein horizontaler Überlauf. Desktop-Dokumentvorschau geprüft. Diese Kontrolle ersetzt keinen Test auf Android-/iOS-Geräten.

## Nicht verifiziert

- Kostenpflichtige Live-Anfragen: keine Benutzer-API-Keys eingesetzt. Anbieter-Verträge sind gemockt; Konto-/Region-/Modellzugriff und Browser-CORS bleiben beim Anbieter zu testen.
- Android/iOS: native Quellen synchronisiert, aber keine APK/AAB/IPA erstellt. JDK/Android SDK bzw. vollständiges Xcode fehlen.
- Docker-Image: Konfiguration erstellt, Docker ist hier nicht verfügbar; Image-Build nicht durchgeführt.
- Endor Dependency Reviewer: Skill gelesen, Endor-MCP/CLI nicht verfügbar. Zusätzliche Endor-Risiko-, Lizenz- und Maintenance-Bewertung **UNKNOWN**, nicht bestanden behauptet. npm/pip-Audits sind davon unabhängige Prüfungen.
- Öffentliche Veröffentlichung, Markenfreigabe, Domainkauf, SMTP, Checkout und Store-Freigabe: nicht erfolgt. www.tafolli.net und info@tafolli.net sind als Betreiberverbindung hinterlegt; keine bestehende Website ersetzt und kein DNS-Eintrag verändert.

Die verbleibenden Betriebs- und Ausbaupunkte stehen in RELEASE.md und MOBILE.md. Der Stand ist eine prüfbare Beta.
