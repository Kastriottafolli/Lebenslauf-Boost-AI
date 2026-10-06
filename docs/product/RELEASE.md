# Release-Status

Stand 06.10.2026. Die Web-App ist unter **https://tafolliboost.com** auf einem DreamHost Self-Managed VPS veröffentlicht; `www` wird auf diese Adresse weitergeleitet. GitHub Pages liefert die aktuelle Oberfläche mit Verbindung zur Produktions-API. Ein veröffentlichter technischer Stand ist keine vollständige kommerzielle, rechtliche oder externe Sicherheitsfreigabe.

## Implementiert und veröffentlicht

Pflichtkonto mit ausdrücklicher AGB-Annahme, E-Mail-Bestätigung und Passwort-Zurücksetzen; bearbeitbares Profil, eigene Unterlagen, Verlauf, Datenexport und geschützte Kontolöschung. Zentral bereitgestellte OpenAI-KI erstellt Lebenslauf, Anschreiben, Motivationsschreiben und E-Mail. Profil-/Abschnittsimport, Faktenbestätigung, Stellenimport mit Textfallback, individuelle Bearbeitung, Kontext bei Revision, Versionsrücksprung, begrenzte Vorschau und PDF/Word/ZIP-Export sind vorhanden. Frühere Anbieteradapter bleiben im Quellcode; die Oberfläche bietet keinen Gasteditor, Nutzer-Key oder Anbietervergleich.

Drei kostenlose Mappen pro Kalenderwoche in Europe/Berlin, getrennte dauerhafte Kaufcredits sowie vorbereitete Einzelkäufe für 1,99 EUR beziehungsweise zehn Mappen für 9,99 EUR. Zahlungsanbieter sind noch nicht aktiviert. Der geschützte Adminbereich besitzt eine eingerichtete MFA-Anmeldung, Nutzerdatenansichten, Nutzungsdiagramm, CSV-Export und Audit-Protokoll. Tatsächliches Hosting bleibt DreamHost; ein Hostinger-Dashboard wurde nicht eingerichtet.

DE/EN/SQ-Oberfläche und Erklärvideos mit KI-Stimme, Musik, Untertiteln und nativen Videosteuerungen; animiertes Boosty-Maskottchen, Willkommensanimation, geführte Hinweise und zentral bereitgestellte Softwarehilfe. Ladeanzeigen zeigen bestätigte Schritte und kennzeichnen die laufende KI-Wartephase. PWA, Ratgeber-SEO und native Android-/iOS-Projektquellen sind vorhanden.

Transaktionsmails werden über eine verschlüsselte Outbox und einen geschützten DreamHost-Mailrelay gesendet. Tatsächliche Zustellung und Aktivierung eines eigenen Produktions-Testkontos wurden geprüft. Tägliche verschlüsselte Sicherungen mit 14 Tagen Aufbewahrung sind eingerichtet; Sicherung und eine getrennte Wiederherstellungsprüfung wurden durchgeführt. Die Sicherungen auf demselben VPS ersetzen keine externe Sicherung.

## Durch externe Informationen bzw. Werkzeuge offen

| Schritt | Was fehlt |
|---|---|
| Marke | tafolliboost.com als Webseite und Boosty als Maskottchen; Namens-/Markenrechte noch prüfen |
| Social-Login | Google-/Apple-/Meta-/X-Apps mit echten Zugangsdaten, Anbieterfreigaben und Callback-Prüfungen; derzeit nur E-Mail-Anmeldung aktiv |
| Sicherheitsabnahme | Externer Penetrations-/Belastungstest; die bisherigen automatisierten Prüfungen sind keine unabhängige Sicherheitsabnahme |
| Externe Sicherung | Kontinuierliche verschlüsselte Offsite-Sicherung und regelmäßige Wiederherstellungsübungen; tägliche lokale Sicherung bereits eingerichtet |
| Betreiber/Datenschutz | Kastriot Tafolli, Anschrift und info@tafolli.net hinterlegt; auf Hosting und Anbieter abgestimmte Datenschutzangaben noch vervollständigen |
| Android | JDK/SDK, Geräteprüfung, Signierung, Play-Console-Konto und Store-Angaben |
| iOS | Vollständiges Xcode, Geräteprüfung, Apple-Team/Signierung, Store-/Datenschutzangaben |
| Store-Grafiken | Native Icons und Startbildschirme vorhanden; reale Store-Screenshots und finale Markenfreigabe fehlen |
| Mailbetrieb | Versandquoten, Bounce-/Spamzustellung und Betrieb dauerhaft überwachen; echte Konto-E-Mails sind eingerichtet |
| Bezahlprodukt | Händlerkonten, Sandbox-End-to-End-Prüfung, Steuer-/Rechnungsablauf und gesetzliche Aufbewahrung; Checkout und Guthabenlogik vorbereitet, Zahlungen deaktiviert, kein Abonnement |
| Größere Skalierung | Gemeinsame Limits und Datenbankmigrationen; Pilotbetrieb mit einem Worker |
| iOS Share-Eingang | Eigene Share Extension fehlt; Einfügen und Deep Links vorhanden |

## Prüfungen

Die automatisierten Tests laufen ohne echte personenbezogene Daten oder kostenpflichtige KI-Aufrufe. Der veröffentlichte Stand besteht 209 Backend- und 43 Frontend-Prüfungen, Build, Lint sowie Abhängigkeitsaudits. Zusätzlich wurden echte Mailzustellung, Aktivierung, Login und die veröffentlichten Videos mit eigenen Testdaten geprüft. Ein grüner Testlauf ersetzt weder Social-Login-/Zahlungsanbieter-Zugriffstests noch mobile Geräte- oder Store-Prüfungen. Weitere Betriebsdetails: [Konto-E-Mails](../deploy/ACCOUNT-MAIL.md), [Wochencredits und Zahlungen](BILLING.md), [Traffic](TRAFFIC.md), [Backups](../deploy/BACKUPS.md), [rechtliche Vorbereitung](LEGAL-READINESS.md).

Vor produktiven Datenbankänderungen eine geprüfte Sicherung erstellen; alte ungeschützte Sitzungen werden nicht stillschweigend neu beansprucht. Bestehende Konten und gespeicherte Bewerbungen wurden durch die additive Aktualisierung erhalten.
