# tafolliboost.com auf DreamHost

Stand 06.10.2026: **https://tafolliboost.com** ist auf einem DreamHost Self-Managed VPS mit Docker/Caddy, persistentem Datenträger und HTTPS veröffentlicht. Der zentrale OpenAI-Zugang, Konto-Mails, Admin-MFA und tägliche verschlüsselte Sicherungen sind eingerichtet. Social-Login-Apps und Zahlungshändler sind noch nicht konfiguriert. Der folgende Ablauf dokumentiert Einrichtung und Wartung; alternative Hosting-Typen sind keine Behauptung über den tatsächlich gewählten Tarif.

## 1. Vorhandenen Hosting-Typ feststellen

Im DreamHost-Panel den Server und den Hosting-Typ der Domain prüfen. Keine bestehenden DNS-, Mail- oder Website-Einstellungen pauschal ersetzen.

| Bestehendes Produkt | Betrieb dieser App |
|---|---|
| Nur Domainregistrierung | Noch kein App-Server. |
| Shared Hosting / statische Website | Statische Informationen möglich, kein dauerhafter FastAPI-Prozess. |
| Managed VPS oder Dedicated | Dauerhafter Prozess mit Panel-Proxy und Prozessverwaltung möglich; Proxy-/Portschutz prüfen. |
| Eigener VPS / DreamCompute mit administrativem Zugriff | TLS-Reverse-Proxy vor isolierter App möglich; vorhandene Docker/Caddy-Konfiguration prüfen. |

[DreamHost verbietet dauerhafte Prozesse auf Shared Hosting](https://help.dreamhost.com/hc/en-us/articles/214869648-Persistent-processes). Der [Panel-Proxy](https://help.dreamhost.com/hc/en-us/articles/217955787-Proxy-Server) ist für Managed VPS und Dedicated vorgesehen. Ein Tarifwechsel ist eine gesonderte Kaufentscheidung, kein Teil einer Dateiübertragung.

## 2. App und private Daten trennen

Die vollständige FastAPI-App liefert auf `https://tafolliboost.com` sowohl die Oberfläche als auch `/api/…` aus. Das vermeidet browserabhängige Cookies zwischen GitHub Pages und einer fremden API-Domain. `_site/` allein enthält keinen Anmeldeserver und keine Datenbank.

Für weitere Übertragungen lässt sich ein geprüftes Quellpaket erzeugen:

```sh
python3 scripts/package_release.py --output /tmp/tafolliboost-source-release.tar.gz
```

Der Helfer verwendet eine Datei-Whitelist und die im aktuellen Arbeitsverzeichnis bearbeiteten Inhalte, einschließlich bereits geänderter Git-Dateien. Er kopiert weder `.git`, private Umgebungsdateien, Kontodatenbanken, Testdaten, virtuelle Umgebungen, `node_modules` noch alte generierte Builds. Mögliche API-/Privatschlüssel im Quelltext führen zum Abbruch, ohne sie auszugeben. Das enthaltene `RELEASE-MANIFEST.json` dokumentiert SHA-256-Prüfsummen. Eine bereits vorhandene Ausgabedatei wird nicht überschrieben. Auf dem Ziel müssen Abhängigkeiten und Frontend-Build noch erzeugt werden; das Archiv ist kein bereits gestarteter Dienst.

Bei einer Installation als Shell-Nutzer liegen Quellcode, Umgebungsdatei und Datenbank außerhalb des DreamHost-Webroots, beispielsweise:

```text
/home/APPUSER/apps/tafolliboost/          Quellcode und frontend/build/
/home/APPUSER/.config/tafolliboost/       private secrets.env, Modus 0600
/home/APPUSER/private/tafolliboost/       Kontodatenbank und Uploads, Modus 0700
```

`APPUSER` ist ein Platzhalter für den tatsächlich vorhandenen Servernutzer. Keine privaten Dateien in `/home/APPUSER/tafolliboost.com/` oder einen anderen direkt ausgelieferten Dokumentenordner kopieren. Beim Docker-Betrieb bleibt die Kontodatenbank im privaten persistenten Volume; diese Trennung ist bereits in `compose.production.yml` vorgesehen.

Serverkonfiguration aus `.env.production.example` ableiten. Mindestens prüfen:

```dotenv
APP_DOMAIN=tafolliboost.com
SITE_URL=https://tafolliboost.com
APP_NAME=tafolliboost.com
ALLOWED_HOSTS=tafolliboost.com,www.tafolliboost.com,localhost,127.0.0.1
ALLOWED_ORIGINS=https://tafolliboost.com,capacitor://localhost,https://localhost
SECURE_COOKIES=true
HOSTED_AI_ENABLED=true
ALLOW_SERVER_KEYS=false
OAUTH_BASE_URL=https://tafolliboost.com
```

Bei einer Shell-Installation zusätzlich absolute private Pfade verwenden:

```dotenv
DATABASE_URL=sqlite:////home/APPUSER/private/tafolliboost/tafolli.db
UPLOAD_DIR=/home/APPUSER/private/tafolliboost/uploads
ADMIN_KEY_FILE=/home/APPUSER/private/tafolliboost/admin-secrets.key
TAFOLLIBOOST_SECRET_FILE=/home/APPUSER/.config/tafolliboost/secrets.env
```

Der Betreiber-OpenAI-Key gehört ausschließlich in die private Serverdatei oder die Prozessumgebung. Keinen Schlüssel in GitHub-Actions-Frontendvariablen, Build-Argumente, URLs, Chat, JavaScript oder öffentlich erreichbare Dateien eintragen. Den zuvor im Chat geteilten Schlüssel vor öffentlichem Betrieb ersetzen. Die lokale Entwicklerdatenbank samt Testkonten wird nicht als Produktionsdatenbank kopiert.

## 3. Laufzeit, HTTPS und dauerhaften Prozess vorbereiten

Python 3.12 und Node.js 22 oder eine gezielt verifizierte kompatible Laufzeit verwenden. Den Frontend-Build mit `SITE_URL=https://tafolliboost.com`, `PUBLIC_BASE_PATH=/` und leerem `PUBLIC_API_BASE` erzeugen. Auf derselben Domain verwendet die App relative API-Aufrufe.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
SITE_URL=https://tafolliboost.com PUBLIC_BASE_PATH=/ PUBLIC_API_BASE= npm run build
```

Die App braucht zunächst nur **einen Worker**: SQLite läuft auf einem lokalen persistenten Datenträger, und ein Teil der HTTP-Ratenbegrenzung ist pro Prozess. Skalierung auf mehrere Worker/Server erfordert eine gemeinsam wirksame Begrenzung und gesonderte Datenbankplanung.

Für einen administrierbaren VPS ist die vorhandene `compose.production.yml` der vorgesehene Ausgangspunkt: Nur der TLS-Proxy veröffentlicht 80/443, der App-Port bleibt im isolierten Container-Netz. Build, HTTP-Weiterleitung, Zertifikat, Serverneustart und Sicherung tatsächlich prüfen, bevor die Domain umgestellt wird. Die `--forwarded-allow-ips "*"`-Einstellung ist ausschließlich für diese isolierte Proxy-App-Verbindung vorgesehen; sie darf nicht auf einen öffentlichen App-Port übertragen werden.

Bei **Managed VPS/Dedicated mit Panel-Proxy** zuerst den konkreten Proxy-Quellhost und Zugriffsschutz feststellen. Laut DreamHost bindet dessen Proxy-Ziel an alle Interfaces auf einem Port zwischen 8000 und 65535; DreamHost stellt standardmäßig keine Port-Firewall bereit. Ein offener HTTP-App-Port wäre deshalb zusätzlich zur HTTPS-Domain direkt erreichbar. Vor Freigabe den Port auf den vertrauenswürdigen Proxy begrenzen oder einen nachweisbar geschützten Betrieb wählen. Weiterleitungsheader ausschließlich von den konkret überprüften Proxy-Adressen vertrauen. Falls der Tarif keinen solchen Schutz erlaubt, ist der isolierte eigene-VPS-Aufbau die geeignetere Variante.

Für den dauerhaften Prozess bietet DreamHost [systemd-Nutzerunits mit linger](https://help.dreamhost.com/hc/en-us/articles/23971547819412-Using-linger-with-Gunicorn) an. Die dortige Gunicorn-Anleitung ist WSGI; diese App ist **ASGI**. Ihre Beispiele nicht unverändert verwenden. Die Unit muss den vorhandenen ASGI-Start `python -m uvicorn backend.main:app` mit einem Worker, den tatsächlich geschützten Bind-/Proxy-Einstellungen und dem richtigen Arbeitsverzeichnis starten. `Restart=on-failure`, `UMask=0077` und eine private Konfigurationsdatei vorsehen. Einen interaktiven SSH-Prozess ohne Neustartverwaltung nicht als fertiges Hosting ausgeben.

Bestehende MX-, SPF-, DKIM- und DMARC-Einträge der E-Mail-Domain erhalten. `www.tafolliboost.com` auf die Hauptadresse weiterleiten. AAAA nur veröffentlichen, wenn der Server über IPv6 tatsächlich erreichbar ist. Keine bestehende Website unter `tafolli.net` ersetzen.

## 4. Google, Apple, Facebook und X aktivieren

DreamHost-Anmeldung und gekaufte Domain erzeugen keine Entwickler-Apps bei den Anmeldediensten. Je Anbieter muss eine eigene App eingerichtet und freigegeben sein. Private Zugangsdaten erst dann auf dem Server setzen:

| Anbieter | Exakte Callback-Adresse | Private Konfiguration |
|---|---|---|
| Google | `https://tafolliboost.com/api/oauth/google/callback` | `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET` |
| Apple | `https://tafolliboost.com/api/oauth/apple/callback` | `OAUTH_APPLE_CLIENT_ID`, `OAUTH_APPLE_CLIENT_SECRET` |
| Facebook | `https://tafolliboost.com/api/oauth/facebook/callback` | `OAUTH_FACEBOOK_CLIENT_ID`, `OAUTH_FACEBOOK_CLIENT_SECRET` |
| X | `https://tafolliboost.com/api/oauth/x/callback` | `OAUTH_X_CLIENT_ID`, `OAUTH_X_CLIENT_SECRET` |

Apple benötigt eine registrierte Services-ID, Domainverifizierung und ein gültiges signiertes, zeitlich begrenztes Client-Secret. Externe Login-Tests nach jeder Aktivierung ausführen. Ohne Konfiguration bleibt der Dienst deaktiviert. Ein zusätzlicher allgemeiner Instagram-Website-Login ist nicht implementiert. Details und Anbieterreferenzen: [HOSTED-OPENAI.md](../product/HOSTED-OPENAI.md).

## 5. GitHub Pages einordnen

Die Workflow-Variablen sind öffentlich sichtbare Build-Konfiguration, keine Geheimnisablage:

| Repositoryvariable | Zweck |
|---|---|
| `SITE_URL` | Tatsächlich veröffentlichte HTTPS-URL für Canonicals und Sitemap. |
| `PUBLIC_BASE_PATH` | `/Lebenslauf-Boost-AI/` bei der Projekt-Page, `/` bei einer Pages-Domain an der Wurzel. |
| `PUBLIC_API_BASE` | Optionaler erreichbarer HTTPS-API-Origin; leer bedeutet statische Vorschau. |

Für den endgültigen Betrieb ist die komplette App auf `tafolliboost.com` vorzuziehen. Eine statische Preview kann auf die App verlinken, sobald diese nachweislich funktioniert. Ein API-Origin im Pages-Build aktiviert keine Datenbank und keine OAuth-Apps. Vor Verwendung einer fremden API-Domain Cookies, CORS, Anmeldung nach Neuladen und OAuth-Rücksprünge im echten Browser testen. Nicht allein auf einen erfolgreichen Netzwerkrequest vertrauen.

## 6. Freigabe durch reale Prüfungen

1. Domain über HTTPS öffnen, Sprachwechsel und rechtliche Seiten laden; keine Vorschau-/Konto-Ladefehler.
2. Eigenes fiktives Testkonto mit ausdrücklicher AGB-Annahme registrieren. Vor Bestätigung muss Login scheitern; danach den tatsächlichen Mail-Einmallink verwenden, anmelden und prüfen, dass der Link nicht erneut nutzbar ist. Passwort-Zurücksetzen über das echte Postfach prüfen: neues Passwort funktioniert, altes Passwort und vorhandene Login-Sitzungen werden ungültig. Fehlerfälle zeigen eine verständliche Meldung.
3. Fiktiven Lebenslauf und Stellenlink verwenden, Daten prüfen, eine Mappe erstellen und speichern. Keine echten Bewerberdaten für diese Prüfung verwenden.
4. Seite neu laden, Konto wieder öffnen, gespeicherte Mappe aufrufen. Danach App-Prozess neu starten und erneut aufrufen: Konten und Verlauf bleiben erhalten.
5. Ein anderes Testkonto darf die Mappe nicht öffnen; anonyme Erzeugungsrequests scheitern. Der öffentliche Browser bekommt keinen Betreiber-Key.
6. Boosty begrüßt freundlich, erklärt die App und beantwortet keine fremden Aufgaben. Aktivierte Social-Logins je Anbieter vollständig bis zur Rückkehr ins Konto prüfen.
7. Private Datenbank, Uploads und Konfigurationsdatei sind von außen nicht per HTTP erreichbar. Direkter App-Port ist ebenfalls abgeschirmt.
8. Datenbanksicherung mit der SQLite-Backup-API erstellen; verschlüsselte externe Kopie und Wiederherstellungsprüfung einrichten. Kein unkoordiniertes Kopieren einer laufenden WAL-Datenbank.
9. Tatsächlichen Hosting-Anbieter, Standort, Aufbewahrung und Verträge in die Datenschutzinformationen aufnehmen; Budgetlimits und OpenAI-Projektlimits prüfen.

Neue E-Mail-Konten werden erst durch einen auslaufenden Bestätigungslink aktiviert. Passwort-Zurücksetzen, neue E-Mail-Adressen und Vertragskopien verwenden die verschlüsselte Mail-Outbox; die frühere Recovery-Code-Anmeldung ist deaktiviert. Der tatsächliche Versand läuft über einen HMAC-geschützten HTTPS-Relay auf dem bestehenden DreamHost Shared Hosting, ohne die Betreiberhomepage zu ersetzen. Mailnutzlasten werden nicht in URLs oder Protokolle geschrieben. Echte Zustellung und Aktivierung eines eigenen Produktions-Testkontos wurden geprüft; Quoten und Spam-/Bouncezustellung müssen laufend beobachtet werden. Details: [ACCOUNT-MAIL.md](ACCOUNT-MAIL.md).

Updates dürfen den privaten Datenträger nicht ersetzen. Erst geprüften Build bereitstellen, Datenbank sichern, Dienst kontrolliert neu starten und funktionierenden Login/Verlauf bestätigen. Das Docker-Volume nicht mit `down -v` löschen. Die vorherige App-Version für einen Rücksprung bereithalten.
