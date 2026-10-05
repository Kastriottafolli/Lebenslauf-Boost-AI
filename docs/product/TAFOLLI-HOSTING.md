# Kastriot Tafolli: Betreiber, Domain und dauerhafte Konten

## Hinterlegt

Kastriot Tafolli, Hauptstraße 1, 18609 Ostseebad Binz, Deutschland. Kontakt: **info@tafolli.net**, Hauptwebsite: **https://www.tafolli.net**. Die Anschrift wurde am 05.10.2026 aus dem bestehenden [Impressum](https://tafolli.net/impressum.html) übernommen. Name/Kontakt erscheinen in der App, im Impressum und in den Datenschutzinformationen; Website-/Mail-Links im Footer und auf Ratgeberseiten.

Die vom Betreiber gekaufte App-Domain ist **https://tafolliboost.com**. Die Produktionsvorlage verwendet diese Adresse für APP_DOMAIN, SITE_URL, ALLOWED_HOSTS und ALLOWED_ORIGINS. **https://www.tafolliboost.com** wird einschließlich Pfad und Query auf die Hauptadresse weitergeleitet. Die Betreiberwebsite www.tafolli.net und info@tafolli.net bleiben bestehen. DNS und Hosting sind noch nicht eingerichtet.

## Datenbank und Anmeldung

Die lokale Konfiguration verwendet `data/tafolli.db`. Die Datei wird nicht ins Git-Repository aufgenommen. Sie enthält Accounts, gehashte Passwörter/Recovery-Codes, ablaufende Login-Tokens, Upload-Sitzungen und ausdrücklich gespeicherte Bewerbungen. API-Keys bleiben ungespeichert. Beim Erstellen eines Kontos wird kein festes gemeinsames Passwort vergeben. Jeder Nutzer registriert seine eigene E-Mail-Adresse und sein eigenes Passwort.

Registrierung und Anmeldung sind bereits vorhanden: **Anmelden → Konto erstellen**. Nach dem Erstellen wird der einmalige Wiederherstellungscode angezeigt. Bewerbungen über **Bewerbung speichern & verfolgen → Auf dem Server speichern** speichern; später über **Meine Bewerbungen** wieder öffnen. Sie bleiben nach Abmelden und nach einem Serverneustart erhalten. Tests verwenden eine getrennte Datenbank.

SQLite nutzt WAL, Fremdschlüsselprüfung, fünf Sekunden Busy-Timeout und eingeschränkte Dateirechte. Das ist ein Ansatz für einen einzelnen Server mit persistentem lokalen Datenträger, keine verifizierte Mehrserver-Konfiguration.

```sh
.venv/bin/python -m backend.manage_database init
.venv/bin/python -m backend.manage_database status
.venv/bin/python -m backend.manage_database backup
```

Backup verwendet die SQLite-Backup-API, prüft die Kopie und überschreibt keine vorhandene Sicherung. Ein automatischer externer Sicherungsdienst ist nicht eingerichtet. Backups verschlüsselt und außerhalb des Servers aufbewahren; Wiederherstellung regelmäßig prüfen. Die Datenbank darf weder in einem öffentlich ausgelieferten Webordner liegen noch per statischem Download erreichbar sein.

## Öffentlicher Betrieb auf eigenem Docker-Server

GitHub Pages liefert ausschließlich die Browser-Version, ohne laufenden Python-Server und Kontodatenbank. Für Konten ist ein FastAPI-fähiger Server mit persistentem Datenträger erforderlich.

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

Kein DNS-/Hostingzugang liegt vor. Es wurde kein öffentlicher Server eingerichtet und keine bestehende Website ersetzt. Docker/Caddy-Start und Zertifikatsausstellung können hier mangels Docker/Server nicht live geprüft werden. info@tafolli.net ist der Betreiber-/Supportkontakt; es wird keine automatische E-Mail versendet. Mail-Verifikation oder Passwort-Reset per E-Mail benötigt einen separat konfigurierten Maildienst. Hostingbezogene Datenschutzangaben und Anbietervereinbarungen vor öffentlichem Betrieb vervollständigen.
