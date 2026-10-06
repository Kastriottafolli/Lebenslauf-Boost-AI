# Boosty AI · Administration und Sicherheitsgrenzen

Der Adminbereich steht im Serverbetrieb unter `/admin` und in der App über **Admin** zur Verfügung. Öffentlich registrierte Konten können keine Adminrechte bekommen. Die E-Mail-Adresse allein ist kein Berechtigungsnachweis. Die serverseitige Berechtigung wird bei jeder Datenabfrage geprüft.

## Anmeldung und Server-Einstellung

Auf **https://tafolliboost.com/admin** erfolgt die Betreiberanmeldung derzeit mit **info@tafolli.net** und dem bestehenden Passwort. Ein Authenticator-Code ist im produktiven Betrieb auf ausdrücklichen Betreiberwunsch nicht erforderlich. Konto-ID, Passwort, Berechtigungen und Daten bleiben erhalten.

`ADMIN_REQUIRE_TOTP=false` schaltet die zusätzliche TOTP-Prüfung ausschließlich in der privaten Serverkonfiguration ab. Ohne diese ausdrückliche Einstellung gilt weiterhin `true`. Der Browser liest nur die erforderlichen Anmeldefelder aus `/api/admin/auth-options`; Benutzer können die Prüfung nicht selbst abschalten. Der Wechsel auf Passwort allein verringert den Schutz bei einem gestohlenen Passwort. Rate-Limits, Admin-Berechtigung, sichere Cookies, 15-Minuten-Sitzungen und Audit-Protokoll bleiben aktiv.

## Ersteinrichtung

Auf dem vorgesehenen App-Server:

```sh
python -m backend.manage_database backup
python -m backend.manage_admin --email info@tafolli.net
```

Der Befehl erstellt ein deaktiviertes, reserviertes Adminkonto. Er zeigt nur den Pfad einer privaten Datei (Dateimodus 0600, außerhalb von Git und Webauslieferung). Darin steht der einmalige Einrichtungscode, gültig für 24 Stunden. Kein Standardpasswort und keine E-Mail mit Zugangsdaten.

Öffne `/admin`, klappe **Ersteinrichtung mit privatem Einrichtungscode** auf und gib E-Mail und Einrichtungscode ein. Lege ein eigenes Passwort mit mindestens 14 Zeichen fest. Bei `ADMIN_REQUIRE_TOTP=false` ist damit die Einrichtung abgeschlossen; der Server gibt keinen Authenticator-Schlüssel an den Browser aus. Bei `true` übertrage zusätzlich den angezeigten Base32-Schlüssel in eine Authenticator-App (TOTP, SHA-1, 6 Ziffern, 30 Sekunden) und bestätige den aktuellen Code. Bewahre diesen Schlüssel privat auf; verwendete Zeitcodes sind nicht wiederverwendbar.

Die verbindliche Betreiber-, Support- und Admin-Adresse ist **info@tafolli.net**. Der produktive Adminbereich ist unter **https://tafolliboost.com/admin** erreichbar. Das Admin-Konto wird ausschließlich serverseitig eingerichtet; eine öffentliche Registrierung mit dieser Adresse vergibt keine Adminrechte. Zugangsdaten und Authenticator-Schlüssel gehören ausschließlich in die private Zugangsdokumentation und einen Passwortmanager.

Die lokale Datenbank und der private Code werden nicht über Git ins Hosting übertragen. Den Admin auf dem Produktionsserver separat einrichten. Verlust oder Ablauf der Einrichtung bzw. des Authenticators: nur mit Serverzugang einen bereits provisionierten Admin zurücksetzen:

```sh
python -m backend.manage_admin --email info@tafolli.net --reset-existing
```

Damit werden bisherige Admin-Sitzungen, Passwort, Authenticator und Einrichtungscode ungültig. Bewerbungen und Konto-ID bleiben erhalten. Ein selbstregistriertes normales Konto wird auch mit diesem Schalter nicht zum Admin. Keine öffentliche Wiederherstellung der Adminrechte.

## Admin-Adresse korrigieren, ohne Zugangsdaten zurückzusetzen

Nach einer Datenbanksicherung kann der Serverbetreiber die Adresse eines bereits aktiven Admin-Kontos korrigieren:

```sh
python -m backend.manage_database backup
python -m backend.manage_admin --rename-from BISHERIGE-ADMIN-EMAIL --email info@tafolli.net
```

Konto-ID, Passwort, Wiederherstellungs-Hash, Authenticator-Schlüssel, MFA-Zähler und zugehörige Daten bleiben erhalten. Die Änderung beendet vorhandene Admin- und normale Anmeldungen und macht veraltete Bestätigungs- oder Zurücksetzungslinks ungültig. Anschließend mit **info@tafolli.net** und dem bisherigen Passwort anmelden; nur bei aktivierter TOTP-Prüfung zusätzlich einen neuen Authenticator-Zeitcode verwenden. Vertragsnachrichten und Sicherheitshinweise werden nicht gelöscht. Die Änderung wird im Admin-Protokoll vermerkt.

Der Befehl lehnt fehlende oder noch nicht aktivierte Admin-Konten sowie belegte Zieladressen ab. Er führt keine Konten zusammen und erhebt normale Konten nicht zu Administratoren. `--rename-from` und `--reset-existing` schließen sich aus; zur reinen Adresskorrektur darf der Zurücksetzungsschalter nicht verwendet werden.

## Ansichten

- Anklickbare Kennzahlen für Kundenkonten, neue/aktive/bestätigte Konten, Bewerbungen und Aufrufe. Heute, gestern, 7/30/90 Tage oder freie UTC-Kalendertage bis 366 Tage; Betreiberkonten werden nicht als Kunden gezählt.
- Kunden mit Namen, E-Mail, Registrierung, letzter Aktivität und Bewerbungszahl; Suche nach Namen/E-Mail, Statusfilter und Seitennavigation. Optionale Profilangaben: Geschlecht, Geburtstag, Adresse, Telefonnummer und gesprochene Sprachen.
- Persönliche Bewerbungsinhalte sowie ursprüngliche CV-/Generierungs-/Nachrichteninhalte einzelner Sitzungen, jeweils bewusst zu öffnen und mit protokolliertem Adminzugriff.
- Nutzungsereignisse mit Konto bzw. anonymem Status, Funktion, Zeitpunkt und HTTP-Ergebnis.
- Admin-Protokoll: Anmeldung, Ersteinrichtung, serverseitiges Zurücksetzen und Datenabfragen.
- Datenbank-Tabellen mit Zeilenzahlen, SQLite-Integritätsprüfung und Verweisen zu den passenden Listen/Support-Editoren. Keine Passwort-Hashes, Tokens, Recovery-Codes, TOTP-Schlüssel oder frei ausführbaren SQL-Befehle im Browser. Vollständige Sicherungen über die Server-CLI.

Datensammlungen sind begrenzt und paginiert; Detailansichten enthalten höchstens 100 Sitzungen/Projekte bzw. Generierungen/Nachrichten. Für größere Bestände Ausbau mit Detail-Paginierung vorsehen. Kein Browser-Endpunkt für einen ungeschützten vollständigen Datenbankdownload.

## Statistik und Datenschutz

Aufrufe und gestartete Sitzungen sind **keine eindeutigen Menschen**. Bots, Reloads, Vorschau und zusätzliche Sitzungen beim Login zählen mit. Ohne Tracking-Identifier oder Fingerprinting kann keine exakte Besucherzahl angegeben werden. Die notwendigen Betriebsereignisse enthalten keine IP-Adressen. Die getrennte freiwillige Besuchsstatistik speichert nach Einwilligung Geräteklasse, ungefähres Land, aktive Zeit und einen gekürzten Netzbereich; siehe [TRAFFIC.md](TRAFFIC.md). Keine vollständigen IP-Adressen, User-Agent-Werte, URLs mit Parametern, Frage-/Dokumenttexte, Passwörter oder API-Keys. Exportereignisse zeigen bereitgestellte Downloads bzw. abgeschlossene Übergaben an den nativen Teilen-Dialog; das tatsächliche Speichern beim Nutzer kann nicht bestätigt werden. Ereignisse werden erst ab diesem Stand erfasst; kein rückwirkender vollständiger Verlauf. Nicht angemeldete Ereignisse bleiben anonym und werden nicht rückwirkend einem Konto zugeordnet.

Funktionsereignisse werden 30 Tage gespeichert, Tagesaggregate und Admin-Protokolle 90 Tage. Kontolöschung entfernt die Kontozuordnung über den Fremdschlüssel. Aggregate bleiben ohne Personenbezug erhalten. Anonyme Inhalte bleiben beim bisherigen 30-Tage-Cleanup; gespeicherte Kontobewerbungen bis zur Löschung. Die App erklärt den Zugriff des Betreibers im Datenschutzdialog. Hosting, Auftragsverarbeitung und die Rechtsgrundlage für diese internen Betriebsstatistiken müssen vor dem öffentlichen Start im tatsächlichen Datenschutztext geklärt werden.

## Schutzmechanismen

- Separater Admin-Token (gehashte Speicherung), eigener HttpOnly-/SameSite-Strict-Cookie, im HTTPS-Betrieb Secure; maximal 15 Minuten. Normale Login-Tokens sind im Adminbereich wirkungslos.
- Optionales MFA (`ADMIN_REQUIRE_TOTP=true`) mit verschlüsseltem TOTP-Secret und atomarem Schutz gegen Code-Wiederverwendung. Fernet-Schlüssel liegt in `data/admin-secrets.key` bzw. `ADMIN_KEY_FILE`, Dateimodus 0600. Den Schlüssel separat und verschlüsselt sichern: eine reine DB-Sicherung reicht für eine Wiederherstellung der Admin-Anmeldung nicht.
- scrypt N=32768, r=8, p=3 (32 MiB), gesalzene versionierte Hashes. Bestehende schwächere Hashes werden bei erfolgreicher Anmeldung aktualisiert.
- 10 Anmeldeversuche pro Identität und 15 Minuten in der Datenbank; zusätzlich HTTP-Limits pro Client/Prozess. Produktionsbetrieb mit einem Worker. Bei größerem Betrieb zentrale Limits und Edge-Schutz ergänzen.
- Admin-API verlangt eigenen Request-Header und prüft den Origin. Native Origins werden kontrolliert zugelassen; die verlinkte Hauptwebsite erhält keinen browserseitigen Zugriff auf Admin-Daten.
- Inhaltsausgabe als Text, CSP, Frame-Schutz, No-Store für API/Admin, Noindex und Ausschluss aus dem Service-Worker. Versionierte App-/CSS-Auslieferung gegen veraltete Cache-Dateien. Der Service-Worker wartet beim Upgrade auf das Schließen alter Tabs und erzwingt kein Neuladen ungespeicherter Bewerbungen.
- HTTPS-Konfiguration mit HSTS, eingeschränkten Hosts, deaktivierter öffentlicher API-Dokumentation, ohne Access-Log/IP-Erfassung im vorgeschlagenen Produktionsstart. Container ohne zusätzliche Linux-Capabilities und ohne neue Privilegien.

Orientierung: [OWASP Passwortspeicherung](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [MFA](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html), [Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html). Die Fernet-Implementierung stammt aus [PyCA cryptography](https://cryptography.io/en/latest/fernet/). Das ist keine Zertifizierung oder Garantie gegen Angriffe.

## Boosty

Boosty ist als animiertes Maskottchen sichtbar, auch mobil. Hinweise begleiten Profil, Stellenbeschreibung, KI und Export. **Boosty fragen** nutzt für angemeldete Nutzer die serverseitig bereitgestellte OpenAI-Anbindung und beantwortet Fragen zur Software. Lokale Hinweise und Begrüßungen stehen auch ohne eine KI-Anfrage zur Verfügung. Antworten und Seitenführung unterstützen Deutsch, Englisch und Albanisch.

Provider-Zugangsdaten bleiben ausschließlich auf dem Server. Die eingegebene Frage und allgemeine Produktanweisungen werden zur Antwortgenerierung übermittelt; die Frage kann selbst sensible Angaben enthalten. Boosty erhält keinen Admin-Zugriff, keine Versandberechtigung und keine frei ausführbaren Aktionen. KI-Antworten können Fehler enthalten.

## Vor öffentlicher Vermarktung noch offen

DreamHost-Hosting, Domain und HTTPS sind in Betrieb. Bestätigungsmails, Passwort-Zurücksetzen, separate Admin-Anmeldung, interne Betriebsstatistiken und verschlüsselte Backups sind eingerichtet und geprüft. Anbieter-Konfiguration für Social-Login und echte Zahlungen, fachliche Prüfung der Rechtstexte und Verträge sowie externe Angriffstests und Belastungstests stehen noch aus. Native Geräte-/Store-Prüfungen fehlen weiterhin. Der Stand ist keine Sicherheitszertifizierung oder vollständige kommerzielle Abnahme.

## Support-Korrekturen

Der Nutzereditor ändert ausschließlich erlaubte Profilfelder. E-Mail, Bestätigungsstatus, Rolle, Guthaben und Passwort können dort nicht direkt überschrieben werden. „Passwort-Link senden“ reiht die reguläre Wiederherstellungs-E-Mail an die vorhandene Nutzeradresse ein und zeigt keinen Token. Betreiber-/Administratorkonten sind in diesen Editoren schreibgeschützt.

Der Bewerbungseditor ändert Titel, Status, Notizen und die vier fertigen Dokumenttexte. Quelldateien, Stellenbeschreibung, Profil-Fakten, Foto und weitere Metadaten bleiben erhalten. Dokumente müssen vollständig und lesbar bleiben. Ein Änderungsgrund ist verpflichtend; Audit-Daten enthalten Grund und Feldnamen, keine Dokumentkopien. Profil-Zeitstempel bzw. Bewerbungsrevision verhindern verlorene parallele Änderungen. Bei Konflikten bleibt der Formularentwurf erhalten und der aktuelle Stand muss bewusst geprüft werden.

Die Datenbankansicht gibt keine beliebigen SQL-Befehle, direkten Rollenänderungen oder vollständigen Datenbankdownloads frei. Die Support-Editoren decken fachliche Korrekturen mit Berechtigungsprüfung und Audit ab; tiefgreifende Wartung erfolgt nach Sicherung über den Serverzugang.
