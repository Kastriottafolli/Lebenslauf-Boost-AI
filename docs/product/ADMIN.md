# Boosty AI · Administration und Sicherheitsgrenzen

Der Adminbereich steht im Serverbetrieb unter `/admin` und in der App über **Admin** zur Verfügung. Öffentlich registrierte Konten können keine Adminrechte bekommen. Die E-Mail-Adresse allein ist kein Berechtigungsnachweis. Die serverseitige Berechtigung wird bei jeder Datenabfrage geprüft.

## Ersteinrichtung

Auf dem vorgesehenen App-Server:

```sh
python -m backend.manage_database backup
python -m backend.manage_admin --email DEINE-ADMIN-EMAIL
```

Der Befehl erstellt ein deaktiviertes, reserviertes Adminkonto. Er zeigt nur den Pfad einer privaten Datei (Dateimodus 0600, außerhalb von Git und Webauslieferung). Darin steht der einmalige Einrichtungscode, gültig für 24 Stunden. Kein Standardpasswort und keine E-Mail mit Zugangsdaten.

Öffne `/admin`, klappe **Ersteinrichtung mit privatem Einrichtungscode** auf und gib E-Mail und Einrichtungscode ein. Übertrage den angezeigten Base32-Schlüssel in eine Authenticator-App: TOTP, SHA-1, 6 Ziffern, 30 Sekunden. Lege ein eigenes Passwort mit mindestens 14 Zeichen fest und bestätige den aktuellen Code. Bewahre den Authenticator-Schlüssel in deinem Passwortmanager auf. Ein verwendeter Zeitcode kann nicht erneut eingesetzt werden; bei einer direkten erneuten Anmeldung auf den nächsten Code warten.

Die lokale Einrichtung wurde für **info@dafoli.net** vorbereitet, entsprechend der ausdrücklich geschriebenen Adresse. Der Betreiber-/Supportkontakt bleibt **info@tafolli.net**. Es wurde keine Mail versendet und keine Domain geändert. Sollte die Adresse korrigiert werden, muss der Betreiber sie lokal ändern oder ein neues Adminkonto gezielt provisionieren.

Die lokale Datenbank und der private Code werden nicht über Git ins Hosting übertragen. Den Admin auf dem Produktionsserver separat einrichten. Verlust oder Ablauf der Einrichtung bzw. des Authenticators: nur mit Serverzugang einen bereits provisionierten Admin zurücksetzen:

```sh
python -m backend.manage_admin --email DEINE-ADMIN-EMAIL --reset-existing
```

Damit werden bisherige Admin-Sitzungen, Passwort, Authenticator und Einrichtungscode ungültig. Bewerbungen und Konto-ID bleiben erhalten. Ein selbstregistriertes normales Konto wird auch mit diesem Schalter nicht zum Admin. Keine öffentliche Wiederherstellung der Adminrechte.

## Ansichten

- Tagesübersicht für 7/30/90 UTC-Kalendertage: registrierte/neue/aktive Konten, Bewerbungen, Aufrufe, gestartete Sitzungen und verwendete Funktionen.
- Nutzer mit E-Mail, Registrierung, letzter Aktivität und Bewerbungszahl; E-Mail-Suche und Seitennavigation.
- Persönliche Bewerbungsinhalte sowie ursprüngliche CV-/Generierungs-/Nachrichteninhalte einzelner Sitzungen, jeweils bewusst zu öffnen und mit protokolliertem Adminzugriff.
- Nutzungsereignisse mit Konto bzw. anonymem Status, Funktion, Zeitpunkt und HTTP-Ergebnis.
- Admin-Protokoll: Anmeldung, Ersteinrichtung, serverseitiges Zurücksetzen und Datenabfragen.
- Datenbank-Tabellen mit Zeilenzahlen und SQLite-Integritätsprüfung. Keine Passwort-Hashes, Tokens, Recovery-Codes, TOTP-Schlüssel oder frei ausführbaren SQL-Befehle im Browser. Vollständige Sicherungen über die Server-CLI.

Datensammlungen sind begrenzt und paginiert; Detailansichten enthalten höchstens 100 Sitzungen/Projekte bzw. Generierungen/Nachrichten. Für größere Bestände Ausbau mit Detail-Paginierung vorsehen. Kein Browser-Endpunkt für einen ungeschützten vollständigen Datenbankdownload.

## Statistik und Datenschutz

Aufrufe und gestartete Sitzungen sind **keine eindeutigen Menschen**. Bots, Reloads, Vorschau und zusätzliche Sitzungen beim Login zählen mit. Ohne Tracking-Identifier oder Fingerprinting kann keine exakte Besucherzahl angegeben werden. Keine IP-Adressen, User-Agent-Werte, URLs mit Parametern, Frage-/Dokumenttexte, Passwörter oder API-Keys in der Statistik. Exportereignisse zeigen bereitgestellte Downloads bzw. abgeschlossene Übergaben an den nativen Teilen-Dialog; das tatsächliche Speichern beim Nutzer kann nicht bestätigt werden. Ereignisse werden erst ab diesem Stand erfasst; kein rückwirkender vollständiger Verlauf. Nicht angemeldete Ereignisse bleiben anonym und werden nicht rückwirkend einem Konto zugeordnet.

Funktionsereignisse werden 30 Tage gespeichert, Tagesaggregate und Admin-Protokolle 90 Tage. Kontolöschung entfernt die Kontozuordnung über den Fremdschlüssel. Aggregate bleiben ohne Personenbezug erhalten. Anonyme Inhalte bleiben beim bisherigen 30-Tage-Cleanup; gespeicherte Kontobewerbungen bis zur Löschung. Die App erklärt den Zugriff des Betreibers im Datenschutzdialog. Hosting, Auftragsverarbeitung und die Rechtsgrundlage für diese internen Betriebsstatistiken müssen vor dem öffentlichen Start im tatsächlichen Datenschutztext geklärt werden.

## Schutzmechanismen

- Separater Admin-Token (gehashte Speicherung), eigener HttpOnly-/SameSite-Strict-Cookie, im HTTPS-Betrieb Secure; maximal 15 Minuten. Normale Login-Tokens sind im Adminbereich wirkungslos.
- MFA mit verschlüsseltem TOTP-Secret und atomarem Schutz gegen Code-Wiederverwendung. Fernet-Schlüssel liegt in `data/admin-secrets.key` bzw. `ADMIN_KEY_FILE`, Dateimodus 0600. Den Schlüssel separat und verschlüsselt sichern: eine reine DB-Sicherung reicht für eine Wiederherstellung der Admin-Anmeldung nicht.
- scrypt N=32768, r=8, p=3 (32 MiB), gesalzene versionierte Hashes. Bestehende schwächere Hashes werden bei erfolgreicher Anmeldung aktualisiert.
- 10 Anmeldeversuche pro Identität und 15 Minuten in der Datenbank; zusätzlich HTTP-Limits pro Client/Prozess. Produktionsbetrieb mit einem Worker. Bei größerem Betrieb zentrale Limits und Edge-Schutz ergänzen.
- Admin-API verlangt eigenen Request-Header und prüft den Origin. Native Origins werden kontrolliert zugelassen; die verlinkte Hauptwebsite erhält keinen browserseitigen Zugriff auf Admin-Daten.
- Inhaltsausgabe als Text, CSP, Frame-Schutz, No-Store für API/Admin, Noindex und Ausschluss aus dem Service-Worker. Versionierte App-/CSS-Auslieferung gegen veraltete Cache-Dateien. Der Service-Worker wartet beim Upgrade auf das Schließen alter Tabs und erzwingt kein Neuladen ungespeicherter Bewerbungen.
- HTTPS-Konfiguration mit HSTS, eingeschränkten Hosts, deaktivierter öffentlicher API-Dokumentation, ohne Access-Log/IP-Erfassung im vorgeschlagenen Produktionsstart. Container ohne zusätzliche Linux-Capabilities und ohne neue Privilegien.

Orientierung: [OWASP Passwortspeicherung](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [MFA](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html), [Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html). Die Fernet-Implementierung stammt aus [PyCA cryptography](https://cryptography.io/en/latest/fernet/). Das ist keine Zertifizierung oder Garantie gegen Angriffe.

## Boosty

Boosty ist wieder als animiertes Maskottchen sichtbar, auch mobil. Acht Hinweise zeigen den Weg durch Profil, Stellenbeschreibung, KI und Export. **Boosty fragen** beantwortet Bedienungsfragen lokal anhand fest hinterlegter DE/EN-Hilfe, ohne Key oder Datenübermittlung. Unbekannte Themen werden als solche gekennzeichnet.

Freie KI-Antworten erfordern einen eigenen Provider-Key und ausdrückliche Zustimmung im Boosty-Dialog. Übermittelt werden nur die eingegebene Frage und allgemeine Produktanweisungen; keine Profilfelder, CV-Dateien, Bewerbungsdokumente, Kontodatensätze oder bisheriger Gesprächsverlauf. Die Frage kann selbst sensible Angaben enthalten; Nutzer entscheiden, was sie eingeben. API-Anfragen können Kosten verursachen. Boosty besitzt keine Aktionen, Tool-Aufrufe, Adminrechte oder Versandfunktion. KI-Antworten können Fehler enthalten.

## Vor öffentlicher Vermarktung noch offen

Öffentliches Hosting/DNS/HTTPS, überprüfte Backups samt Wiederherstellung und Schlüsselverwaltung, Hosting-/Datenschutzerklärung, Mail-Verifikation/SMTP, externe Angriffstests und Belastungstests unter realen Bedingungen. Native Geräte-/Store-Prüfungen fehlen weiterhin. Der geprüfte Stand ist eine Beta, keine vollständig abgenommene kommerzielle Infrastruktur.
