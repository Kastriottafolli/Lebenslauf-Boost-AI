# Android und iOS: vorhandene Projekte und Veröffentlichung

## Implementiert

- `android/`: Capacitor-Projekt, Kamera-/Datei-/Share-Plugins, kein Android-Cloud-Backup, Empfang von `ACTION_SEND text/plain` für HTTPS-Stellenlinks, eigener `candidaro:`-Deep-Link.
- `ios/`: Xcode-Projekt mit Swift-Package-Anbindung, Kamera-/Fotobibliothek-Begründungen, URL-Schema und Privacy Manifest für Dateizeitstempel. Der Manifest-Eintrag ist dem Resources-Target hinzugefügt.
- Kamera-/Foto-Scan → lokale Tesseract-OCR → prüfbares Profil. Keine externe OCR-API.
- PDF/Word/ZIP → native Cache-Datei → systemeigener Teilen-Dialog. Private API-Keys werden nicht auf dem Gerät gespeichert.
- Eigene Android/iOS-Icons und Startbildschirme; reproduzierbar mit `python scripts/native_icons.py` (Pillow).
- Native Zurück-Taste und App-Deep-Link `candidaro://job?jobUrl=https%3A%2F%2Fexample.com%2Fjob`.

iOS hat derzeit **keine eigene Share Extension für eingehende Safari-Links**. Dort funktionieren Link-Einfügen und Deep Links. Ein zusätzliches Extension-Target wäre ein eigener Ausbau.

## Lokal geprüft

`npx cap add android`, `npx cap add ios` und `npx cap sync` erfolgreich. Apple-Plists und Xcode-Projekt wurden syntaktisch mit `plutil` geprüft.

Auf diesem Rechner fehlen vollständiges Xcode, ein JDK und das Android SDK. Es wurden deshalb weder APK/AAB/IPA gebaut noch Kamera, Teilen, AppUrlOpen oder Share-Intents auf Geräten ausgeführt. Web-OCR und Dokumentexport werden separat im Browser geprüft.

## Nächste externe Schritte

1. Android Studio mit SDK/JDK bzw. Xcode installieren; vorhandene Projektdateien öffnen.
2. Bundle-/Application-ID, Anzeigename, reale Domain und Store-Konten festlegen. `net.tafolli.candidaro` ist vorläufig.
3. Bei Serverbetrieb mit `SITE_URL=https://tafolliboost.com PUBLIC_BASE_PATH=/ PUBLIC_API_BASE=https://tafolliboost.com npm run mobile:sync` bauen. Die App-Ursprünge im Server konfigurieren; Bearer-Login für native Requests testen.
4. Geräteprüfungen: Kameraabbruch, große Scans, OCR-Zahlenfehler, Fotoauswahl, Offline-Demo, Export/Share, Deep Links, Android Share-Intent und Tastatur/Safe Areas.
5. Store-Screenshots, Beschreibung, Support-/Datenschutz-URL und Datenangaben vervollständigen. App-Icons und Startbildschirme verwenden bereits die vorläufige Marke.
6. Android Release-AAB signieren; iOS Archive mit eigenem Apple-Team signieren und TestFlight testen.
7. Erst nach Prüfung veröffentlichen. Native Mehrwerte sind umgesetzt, eine Store-Zulassung ist damit nicht garantiert.

Offizielle Quellen: [Capacitor](https://capacitorjs.com/docs/getting-started), [Kamera](https://capacitorjs.com/docs/apis/camera), [Dateien/Privacy Manifest](https://capacitorjs.com/docs/apis/filesystem), [Apple Mindestfunktionalität](https://developer.apple.com/app-store/review/guidelines/#minimum-functionality).
