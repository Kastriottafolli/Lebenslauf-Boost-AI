# Boosty: Design, Chat und Kontoverlauf

## Abgearbeiteter Workflow

1. [x] Alte GitHub-Pages-App im Browser und ihre Gleit-Tour in `frontend/js/ui/mascot.js` prüfen.
2. [x] Boostys Dokumentfigur als hochwertige 3D-Illustration weiterentwickeln und als Projektdatei speichern.
3. [x] Website, Administration, Ratgeber, Rechtsseiten, Favicon und PWA-Icon auf dieselbe Figur und Blau-/Marinefarben abstimmen.
4. [x] Präsenz in Startseite, Navigation, Schrittbegleitung, Chat und Ladeansicht integrieren. Bewegungen respektieren `prefers-reduced-motion`.
5. [x] Chat mit Gesprächsblasen, Enter zum Senden, Shift+Enter für Zeilenumbrüche, Antwortstatus und einzelnen Navigationsaktionen ergänzen.
6. [x] Einstieg mit Registrierung, Login und Gastmodus; angemeldete Nutzer erhalten einen Einstieg in ihren Verlauf.
7. [x] Entwürfe und Mappen automatisch speichern; Firma, Position, Erstellungsdatum und Status im durchsuchbaren Kontoverlauf anzeigen.
8. [x] Kontoschutz, erneuten Login, konkurrierende Änderungen, mobile Darstellung und Sprachwechsel prüfen.

## Figur und Gestaltung

`static/boosty-3d.png` ist eine transparente 1254 × 1254 PNG-Illustration, erstellt mit der integrierten Imagegen-Funktion anhand der bisherigen Figur (`static/icon-512.png`). Das Original der Generierung bleibt unverändert erhalten. Wiedererkennung: weißes Dokument, blauer Kopfbereich, drei Textlinien, freundliches Gesicht und erhobene Hand. Die Website animiert die Illustration mit Schweben, Neigen und einem kurzen Sprung beim Schrittwechsel. Es handelt sich um eine 3D-Illustration mit CSS-Bewegungen.

Prompt-Kern: „Premium 3D character for a professional resume application; preserve friendly white document, cobalt top band, three resume lines, expressive dark eyes, slim arms, rounded hands and blue feet; welcoming raised hand; satin ceramic materials, bevels, soft studio light and ambient occlusion; single full-body mascot on a transparent background, no text.“

Farben: Cobalt `#0878df`, Marine `#142c49`, Akzent `#0864bc`, Hintergrund `#f5f8fd`. Dokument-Designs behalten ihre eigenen exportierten Farbschemata.

Die Begleitung bewegt sich neben dem bearbeiteten Bereich, wenn dort Platz frei ist. Sie prüft sichtbare Eingaben, Buttons und Vorschauflächen auf Überschneidung. Bei wenig Platz erscheint sie direkt vor dem betreffenden Feld im Seitenfluss. Auf kleinen Displays ist die Begleitung eingebettet; ein eigener Chatbutton bleibt an ihr verfügbar. Der separate Chatstarter nutzt freie Bildschirmbereiche und wird zeitweise ausgeblendet, wenn er Bedienelemente verdecken würde. Begleitung kann abgeschaltet werden.

## Chat und Betreiber-KI

Der Chat hält maximal 60 Gesprächsblasen ausschließlich im Arbeitsspeicher des offenen Tabs. Nachrichten werden bei Abmeldung entfernt. Lokale Antworten erscheinen unmittelbar. Bei aktivierter und erlaubter Betreiber-KI erscheint während der Anfrage ein Antwortstatus. Jede geeignete Antwort bietet eine feste, freigegebene „Zeig mir“-Aktion. Texte und Fragen werden als Text ausgegeben, niemals als Benutzer-HTML.

Die separate OpenAI-Anbindung bleibt eine beschränkte Themenerkennung: nur die aktuelle Frage wird nach Zustimmung übertragen; Antworten stammen aus der geprüften DE/EN/SQ-Hilfe. Der Anbieter erhält keine Lebenslaufdaten oder Chat-Historie. Boosty kann nicht programmieren, andere Themen bearbeiten, Konten verändern oder E-Mails verschicken. Erkennbar eingefügte Zugangsdaten werden vor einer Anbieteranfrage abgefangen; dieser Filter ersetzt nicht den Hinweis, keine Geheimnisse in den Chat zu schreiben.

Die Betreiber-KI benötigt weiterhin die private Serverkonfiguration aus [BOOSTY-SETUP.md](BOOSTY-SETUP.md). Ohne Betreiber-Key funktionieren lokale Antworten und Begleitung. Es wurde kein echter Anbieteraufruf für diese Änderung durchgeführt.

## Speicherung und Verlauf

Nach Anmeldung speichert der Editor Eingaben mit 900 ms Verzögerung. Gespeichert werden Profil, Stellenanzeige, Wünsche, optionales Foto, Dokumente, Sprache, Design, Anbieter-/Modellwahl, Arbeitsschritt, Status und Notizen. API-Keys und Chattexte sind vom Projektschema ausgeschlossen. Eine Anmeldung zeigt diese Speicherung ausdrücklich an; der Gastmodus bietet keine automatische Kontospeicherung.

Angefangene Projekte können leere Quellen und noch keine Dokumente enthalten. Die Erstellung von KI-Dokumenten verlangt weiterhin die bisherigen vollständigen Eingaben und die Profilbestätigung. Ein Entwurf wird bei der ersten Generierung zur Mappe; eine erneute erfolgreiche Generierung einer vorhandenen Mappe erzeugt einen weiteren Eintrag. Fehlgeschlagene Generierungen erzeugen keinen solchen Eintrag. Beim Generieren pausiert die Speicherung, bis der neue Zustand vollständig bereitsteht.

Öffnen, neue Bewerbung und Abmelden warten auf ausstehende Speicherung. Fehler bleiben sichtbar; das Schließen eines Tabs mit noch offenen Änderungen löst eine Warnung aus. Die Anzeige „gespeichert“ erscheint nach einer erfolgreichen Serverantwort. Fotos und Quelltexte werden nach Wiederanmeldung wiederhergestellt. Einzelne Bewerbungen und das Konto sind löschbar.

Der Kontoverlauf zeigt Bewerbungen und ihren aktuellen Bearbeitungsstand. Er speichert nicht jede einzelne Tastatureingabe als separate Version. „Versendet“ ist eine vom Nutzer gesetzte Markierung, keine Bestätigung eines E-Mail-Versands.

Die bestehende Tabelle `applications` wird weiterverwendet; Zusatzinformationen liegen im validierten JSON. Es ist keine neue Datenbanktabelle oder Migration erforderlich. Eigentumsprüfungen gelten unverändert. Zeitstempel und Revisionsnummern erzeugt der Server. Updates einer versionierten Bewerbung benötigen die aktuelle Revision; ein veralteter Tab erhält HTTP 409. Die SQLite-Schreibtransaktion verhindert, dass zwei gleichzeitige Updates dieselbe Revision übernehmen. Bestehende unversionierte Projekte werden beim ersten Update versioniert.

Die Datenschutzhinweise wurden auf automatische Kontospeicherung, Fotos und den Chat im Arbeitsspeicher abgestimmt. Die bereits vorhandenen offenen Betreiber-/Hostingangaben bleiben als Entwurf gekennzeichnet.

## Validierung

- 62 Backendtests und 22 Frontendtests bestanden; inklusive Erhalt nach erneutem Login, fremdem Zugriff, Dokument-/Design-/Wunscherhalt, Revisionskonflikten, parallelen Schreibversuchen und Zugangsdatenfilter.
- Produktionsbuild und Ruff-Prüfung bestanden.
- Browserprüfung mit getrenntem synthetischem Testkonto auf einer eigenen Vorschau-Datenbank: Entwurf automatisch gespeichert, nach Neuladen geöffnet, Demo erzeugt, Sapphire gespeichert, abgemeldet und nach erneutem Login samt Dokumenten wiederhergestellt.
- Chat: direkte Softwareantwort, sichtbarer Gesprächsverlauf, Ablehnung eines Programmierauftrags und albanische Hilfe geprüft.
- Mobile Prüfung bei 390 × 844: keine horizontale Überbreite, eingebettete Begleitung und freie Exportbuttons. Keine echten Bewerbungsdaten oder Anbieter-Keys eingesetzt.
- Android-/iOS-Webressourcen können per `npm run mobile:sync` aktualisiert werden. Installation auf echten Geräten und Store-Veröffentlichung sind gesonderte Schritte.

## Eigenständiger Einstieg

Beim ersten anonymen Aufruf ist ausschließlich die Startansicht sichtbar: Boosty, kurze Erklärung und Konto erstellen / Einloggen / Als Gast weitermachen. Der Editor ist bereits im HTML `hidden`, damit er auch vor dem Laden von JavaScript nicht sichtbar wird. Informationen und FAQ öffnen separat im Informationsdialog. Erst eine bewusste Gastwahl oder eine erfolgreiche Kontoanmeldung/-registrierung öffnet das Studio. Eine gültige bestehende Anmeldung führt direkt ins Studio; Abmelden und Kontolöschung schließen die Kontoansicht und kehren zum Einstieg zurück. Geteilte Stellenlinks dürfen den Editor vor dieser Wahl nicht aufdecken.
