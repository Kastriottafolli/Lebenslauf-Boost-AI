# Kastriot Tafolli: Betreiber, Domain und dauerhafte Konten

## Hinterlegt

Kastriot Tafolli, Hauptstraße 1, 18609 Ostseebad Binz, Deutschland. Kontakt: **info@tafolli.net**, Hauptwebsite: **https://www.tafolli.net**. Die Anschrift wurde am 05.10.2026 aus dem bestehenden [Impressum](https://tafolli.net/impressum.html) übernommen. Name/Kontakt erscheinen in der App, im Impressum und in den Datenschutzinformationen; Website-/Mail-Links im Footer und auf Ratgeberseiten.

Die vom Betreiber gekaufte App-Domain ist **https://tafolliboost.com**. DNS, DreamHost Self-Managed VPS und HTTPS sind eingerichtet. Die Produktionskonfiguration verwendet diese Adresse für APP_DOMAIN, SITE_URL, ALLOWED_HOSTS und ALLOWED_ORIGINS. **https://www.tafolliboost.com** wird einschließlich Pfad und Query auf die Hauptadresse weitergeleitet. Die Betreiberwebsite www.tafolli.net und info@tafolli.net bleiben bestehen. Die übernommenen Betreiberangaben und zugehörigen Verträge müssen weiterhin bestätigt und fachlich geprüft werden.

## Datenbank und Anmeldung

Die lokale Konfiguration verwendet `data/tafolli.db`; die Produktionsdatei liegt im privaten persistenten Docker-Volume. Sie wird nicht ins Git-Repository aufgenommen. Die Datenbank enthält Accounts, scrypt-Passwort-Hashes, ablaufende Login-Tokens, gehashte Einmallinks, temporär verschlüsselte Mailnutzlasten, Upload-Sitzungen, gespeicherte Bewerbungen und Guthaben. Betreiber-API-Keys liegen in der privaten Serverumgebung und werden nicht in der Datenbank gespeichert. Beim Erstellen eines Kontos wird kein festes gemeinsames Passwort vergeben. Jeder Nutzer registriert seine eigene E-Mail-Adresse und sein eigenes Passwort.

Registrierung und Anmeldung sind vorhanden: **Konto erstellen**, AGB ausdrücklich annehmen, Bestätigungslink im eigenen Postfach öffnen und anschließend anmelden. Passwort-Zurücksetzen erfolgt per E-Mail-Einmallink, nicht mehr über den früheren Wiederherstellungscode. Das Konto bietet Profil, Unterlagen, Verlauf, Guthaben, Sicherheit und Datenexport. Erfolgreiche Bewerbungsmappen werden vor der API-Antwort im eigenen Verlauf gespeichert; eigene Entwürfe und Änderungen können ebenfalls gespeichert werden. Sie bleiben nach Abmelden und nach einem Serverneustart erhalten. Automatisierte Tests verwenden eine getrennte Datenbank.

SQLite nutzt WAL, Fremdschlüsselprüfung, fünf Sekunden Busy-Timeout und eingeschränkte Dateirechte. Das ist ein Ansatz für einen einzelnen Server mit persistentem lokalen Datenträger, keine verifizierte Mehrserver-Konfiguration.

```sh
.venv/bin/python -m backend.manage_database init
.venv/bin/python -m backend.manage_database status
.venv/bin/python -m backend.manage_database backup
```

Der Verwaltungsbefehl erzeugt eine SQLite-Kopie; im Produktionsbetrieb wird zusätzlich der eigene verschlüsselte Backup-Helfer täglich um 03:30 UTC verwendet. Er prüft die Sicherung, überschreibt keine vorhandene Datei und bewahrt Sicherungen 14 Tage auf. Ein echter Sicherungslauf und eine getrennte Wiederherstellungsprüfung wurden durchgeführt. Ein automatischer externer Sicherungsdienst ist noch nicht eingerichtet. Verschlüsselte Sicherungen zusätzlich außerhalb des Servers aufbewahren und Wiederherstellung regelmäßig prüfen. Die Datenbank darf weder in einem öffentlich ausgelieferten Webordner liegen noch per statischem Download erreichbar sein. Details: [BACKUPS.md](../deploy/BACKUPS.md).

## Öffentlicher Betrieb auf eigenem Docker-Server

GitHub Pages liefert ausschließlich die Browser-Oberfläche und ist im aktuellen Build mit der Produktions-API verbunden. Auf Pages selbst laufen weder Python-Server noch Kontodatenbank. Diese liegen auf dem DreamHost-VPS mit persistentem Datenträger. Die folgende Anleitung beschreibt Einrichtung und spätere Wartung dieses Serverbetriebs.

1. Hostingzugang und Server-IP bereitstellen. Beim Domainanbieter `@` (tafolliboost.com) als A-Eintrag auf die Server-IP setzen und `www` per CNAME auf tafolliboost.com verweisen lassen (oder ebenfalls als A-Eintrag). AAAA nur mit funktionierendem IPv6 setzen. Bestehende E-Mail-/MX-Einträge beibehalten.
2. Projekt auf den Server bringen, `.env.production.example` als private `.env.production` kopieren und die vier Adressfelder oben prüfen.
3. Ports 80/443 für den Proxy freigeben. Der App-Container bekommt keinen öffentlichen Port.
4. Starten:

```sh
docker compose --env-file .env.production -f compose.production.yml up --build -d
docker compose --env-file .env.production -f compose.production.yml exec app python -m backend.manage_database status
```

SEO-Build: `SITE_URL=https://tafolliboost.com PUBLIC_BASE_PATH=/ npm run build` erzeugt Canonicals, Sprachverweise, Open-Graph-URL und Sitemap auf der neuen Domain. Der Docker-Build übernimmt SITE_URL aus der Produktionskonfiguration.

Caddy verwendet info@tafolli.net als Zertifikatskontakt und bedient die konfigurierte App-Domain mit automatischem HTTPS, sobald DNS und Erreichbarkeit passen. Der Proxy ist die einzige öffentliche Eingangsstelle. Forwarded-Header werden nur in dieser isolierten Container-Konfiguration akzeptiert; den App-Port dabei nicht direkt veröffentlichen. [Caddy-Proxy-Dokumentation](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

Das benannte Docker-Volume `app-data` erhält die Konten über Neustarts und normale Rebuilds. `docker compose down -v` würde die persistenten Volumes löschen und gehört nicht zum normalen Update.

Vor Freigabe: Testkonto registrieren → Bewerbung speichern → abmelden → neu anmelden → Bewerbung öffnen → Container neu starten und erneut prüfen. Echte Nutzer erst auf dem HTTPS-Server anmelden lassen.

## Offen

Domain, Docker/Caddy und HTTPS sind öffentlich in Betrieb; die bestehende Betreiberhomepage wurde nicht ersetzt. info@tafolli.net ist der öffentliche Betreiber-/Supportkontakt und feste Absender des geschützten Konto-Mailrelays. Bestätigungs-, Passwort-Zurücksetzungs- und Vertrags-E-Mails sind eingerichtet. Echte Zustellung und Aktivierung eines eigenen Testkontos wurden geprüft.

Offen bleiben konfigurierte und freigegebene Social-Login-Apps, Händlerkonten und Zahlungsprüfung, externe Sicherungen sowie die Bestätigung der Betreiberangaben und erforderlichen Anbietervereinbarungen. Android/iOS benötigen weiterhin Geräteprüfung, Signierung und Store-Veröffentlichung. Das Hosting bleibt DreamHost; ein Hostinger-Traffic-Dashboard wurde nicht eingerichtet. Die MFA-geschützte App-Adminübersicht stellt Nutzungsdiagramm und CSV-Export bereit: [TRAFFIC.md](TRAFFIC.md).
