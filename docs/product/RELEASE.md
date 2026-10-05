# Release-Status

Diese Änderung baut einen funktionsfähigen Beta-Stand. Sie ist keine Behauptung, dass ein öffentliches, kommerzielles Produkt bereits vollständig betrieben und freigegeben ist.

## Implementiert und lokal prüfbar

Profil-/Abschnittsimport, Faktenbestätigung, Stellenimport mit Textfallback, fünf KI-Adapter mit Modellwahl/Key-Links, explizite Demo, vier Dokumente, individuelle Bearbeitung, Vergleich, Kontext bei Revision, Versionsrücksprung, Vorschau, PDF/Word/ZIP, E-Mail-Entwurf, Konten/Recovery, Projektspeicherung/Status/Notizen/Löschung, PWA, DE/EN, Ratgeber-SEO und native Projektquellen.

## Durch externe Informationen bzw. Werkzeuge offen

| Schritt | Was fehlt |
|---|---|
| Marke/Domain | Registrar-Kauf und finale Namens-/Markenprüfung; keine Domain ist reserviert |
| Öffentlicher Server | Hosting/HTTPS, finale Host-/Origin-Liste, verschlüsselte externe Backups; Cleanup beim Start und stündlich integriert |
| Betreiber/Datenschutz | Kastriot Tafolli, Anschrift und info@tafolli.net hinterlegt; auf Hosting und Anbieter abgestimmte Datenschutzangaben noch vervollständigen |
| Live-KI | Eigene gültige Keys, Guthaben und Modellzugriff; bisher Vertragstests mit Mocks |
| Android | JDK/SDK, Geräteprüfung, Signierung, Play-Console-Konto und Store-Angaben |
| iOS | Vollständiges Xcode, Geräteprüfung, Apple-Team/Signierung, Store-/Datenschutzangaben |
| Store-Grafiken | Native Icons und Startbildschirme vorhanden; reale Store-Screenshots und finale Markenfreigabe fehlen |
| Mail-Verifikation | SMTP bzw. Identity-Anbieter; derzeit Recovery-Code statt Mail-Reset |
| Bezahlprodukt | Noch kein Checkout/Abonnement; serverfinanzierte KI braucht zusätzliche Tagesquoten und Abrechnung |
| Größere Skalierung | Gemeinsame Limits und Datenbankmigrationen; Pilotbetrieb mit einem Worker |
| iOS Share-Eingang | Eigene Share Extension fehlt; Einfügen und Deep Links vorhanden |

## Prüfungen

Die automatisierten Tests laufen ohne echte personenbezogene Daten oder kostenpflichtige KI-Aufrufe. Die abschließenden Ergebnisse und Browserprüfungen stehen im Änderungsbericht/PR. Ein grüner Testlauf ersetzt weder Anbieter-Zugriffstests noch mobile Geräte- oder Store-Prüfungen.

Vor dem ersten produktiven Datenbankstart Backup erstellen; alte ungeschützte Sitzungen werden nicht stillschweigend neu beansprucht.
