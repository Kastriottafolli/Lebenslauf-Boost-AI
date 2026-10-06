# Verschlüsselte SQLite-Sicherungen

`python -m backend.backup` erzeugt einen konsistenten SQLite-Snapshot über die SQLite-Backup-API. Auch noch nicht in die Hauptdatei übertragene WAL-Daten werden berücksichtigt. Ein in RAM erstelltes Archiv mit Datenbank, Metadaten und gegebenenfalls den passenden Admin- und Mail-Fernet-Schlüsseln wird mit einem **separaten** Fernet-Backupschlüssel verschlüsselt. Private Admin-Setup-Anleitungen und Einrichtungstokens werden nicht als Dateien beigefügt; noch gültige Setup-Hashes können wie andere Kontodaten in der Datenbank enthalten sein.

Der Backupschlüssel ist eine privat erzeugte Fernet-Schlüsseldatei mit Dateimodus `0600`. Er muss außerhalb des Datenbank- und Sicherungsverzeichnisses liegen und separat sicher aufbewahrt werden. Ohne diesen Schlüssel können Sicherungen nicht wiederhergestellt werden. Das Backupverzeichnis muss `0700` haben; Archive werden ausschließlich neu mit `0600` angelegt. Vorhandene Archive werden nie überschrieben. In Docker benötigt der Backupaufruf eigene private Mounts für Schlüssel und Sicherungsziel; die privaten Hostdateien und das Sicherungsverzeichnis müssen vor dem Lauf eingerichtet sein.

`compose.production.yml` enthält dafür den nur ausdrücklich gestarteten Dienst `backup` im Profil `maintenance`. Er verwendet das zuvor gebaute Image `tafolliboost-app` beim Compose-Projektnamen `tafolliboost`, hat keinen Netzwerkzugriff und bekommt das Datenvolume nur lesend. Nur dieser Wartungsdienst bekommt `/opt/tafolliboost/private/backup.key` und das schreibbare Sicherungsziel `/opt/tafolliboost/private/backups`; der normale App-Dienst erhält den Backupschlüssel nicht. Die privaten Hostpfade sind vor dem Start mit passenden Eigentümern vorzubereiten: Schlüssel `0600`, Sicherungsziel `0700`, jeweils UID 1000 des App-Images. Das Host-Elternverzeichnis kann für den Serveradministrator `0700` bleiben.

```sh
docker compose --project-name tafolliboost \
  --env-file .env.production -f compose.production.yml \
  --profile maintenance run --rm --no-deps backup
```

Der Lesezugriff auf eine aktive WAL-Datenbank ist mit bereits vorhandenen lesbaren WAL-/SHM-Dateien getestet. Die App muss für den vorgesehenen täglichen Sicherungslauf ihre Datenbank geöffnet halten. Fehlende WAL-/SHM-Dateien bei einer vollständig gestoppten Instanz können einen separaten lesenden WAL-Zugriff verhindern; der Helfer scheitert dann ausdrücklich und nutzt keine unsichere `immutable`-Umgehung, die aktuelle WAL-Daten ignorieren könnte. Den tatsächlichen Wartungscontainer und die Wiederherstellung vor dem geplanten Betrieb prüfen.

```sh
python -m backend.backup create \
  --database /app/data/tafolli.db \
  --admin-key /app/data/admin-secrets.key \
  --key-file /run/backup/encryption.key \
  --directory /app/backups \
  --retention-days 14

python -m backend.backup verify \
  --archive /app/backups/tafolliboost-backup-ZEITSTEMPEL.fernet \
  --key-file /run/backup/encryption.key
```

Wenn noch kein Admin eingerichtet ist, kann `--admin-key` entfallen. Sobald die Datenbank Admin-Datensätze enthält, ist der passende Schlüssel erforderlich und wird durch Entschlüsselung der gespeicherten Admin-Secrets geprüft. Eine reine Datenbanksicherung würde für die Wiederherstellung dieser Admin-Anmeldung nicht ausreichen.

Jede neue Sicherung wird vor und nach dem Schreiben entschlüsselt geprüft: erlaubte Archivbestandteile, SQLite-Integrität sowie passende Admin- und Mail-Schlüssel. `verify` liest nur das Archiv und den Backupschlüssel; es extrahiert nichts und überschreibt keine laufende Datenbank. Ein falscher Schlüssel, beschädigtes Archiv oder unerwartete Inhalte führen zum Fehler. Inhalt und Schlüssel werden nicht im Terminal ausgegeben.

Nach einer erfolgreich geprüften neuen Sicherung entfernt der Helfer nur reguläre Dateien im ausdrücklich angegebenen Verzeichnis, deren Name exakt dem eigenen Muster `tafolliboost-backup-UTCZEITSTEMPEL.fernet` entspricht und deren Zeitstempel älter als 14 Tage ist. Andere Dateien, Unterverzeichnisse und Symlinks bleiben erhalten. Die Aufbewahrung greift deshalb erst beim nächsten erfolgreichen Sicherungslauf; ausgefallene oder gestoppte Läufe verkürzen die Frist nicht automatisch. Schlüsselwechsel erfordern die separate Aufbewahrung der früheren Schlüssel, solange damit verschlüsselte Sicherungen existieren.

Die Lösung ist für eine einzelne lokale SQLite-Instanz ausgelegt. Der Snapshot ist auf **256 MiB Datenbankgröße**, die verschlüsselte Datei auf **512 MiB** und die Snapshot-Erstellung auf **120 Sekunden** begrenzt. Größere Datenbanken benötigen eine andere geprüfte Sicherungslösung. Der CLI-Helfer bringt keinen eigenen Scheduler, externen Sicherungsdienst oder automatischen Wiederherstellungsdienst mit. Root-/SSH-Zugang, Datenträger und Backupschlüssel müssen separat geschützt sein. Ein Backup im selben Server schützt nicht vor einem vollständigen Serververlust.

Auf dem DreamHost-Produktionsserver ist ein Root-Cronjob täglich um **03:30 UTC** eingerichtet; die Host-Zeitzone ist `Etc/UTC`. Er ruft `/usr/local/sbin/tafolliboost-backup` auf. Der Wrapper verhindert parallele Läufe mit `flock`, arbeitet über den aktuellen Release-Link `/opt/tafolliboost/current` und startet den Compose-Wartungsdienst mit dem Projektnamen `tafolliboost` und dem Profil `maintenance`. Die Ausgabe liegt unter `/opt/tafolliboost/private/backup.log`; `logrotate` rotiert dieses Betriebsprotokoll wöchentlich, bewahrt vier rotierte Dateien auf und komprimiert sie. Ein echter Wartungscontainer hat die Sicherung erstellt und geprüft. Die Wiederherstellung wurde zusätzlich auf dem Rechner des Betreibers in eine getrennte temporäre SQLite-Datei geprüft, einschließlich SQLite-Integrität und reserviertem Admin-Konto; die lokale Prüfkopie wurde anschließend gelöscht.

Für eine manuelle Wiederherstellung zunächst `verify` ausführen und die App kontrolliert stoppen. Das authentifizierte Archiv in einer privaten Umgebung entschlüsseln; nur `database.sqlite3`, `admin-secrets.key` und gegebenenfalls `mail-secrets.key` in eine neue private Wiederherstellungsumgebung übernehmen, Rechte `0600` und Eigentümer prüfen. Datenbank, Admin-Schlüssel und Mail-Schlüssel gehören zusammen. Der Mail-Schlüssel erhält verschlüsselte ausstehende Bestätigungen, Zurücksetzungslinks und Vertragskopien. Fehlende oder unpassende Schlüssel brechen die Sicherung ab, wenn betroffene Datensätze vorhanden sind. Neue Archive verwenden Format 2; ältere Archive mit Format 1 bleiben prüfbar. Einen Wiederherstellungstest zunächst mit einer getrennten App-/Datenbankinstanz durchführen. Für ein Ersetzen der Produktionsdatenbank erst den bestehenden Datenträger sichern und die alte SQLite-Verbindung einschließlich WAL schließen. Keine Live-Datenbank durch Kopieren überschreiben. Löschungen seit dem Sicherungszeitpunkt müssen vor erneuter Freigabe berücksichtigt werden. Gesicherte Login-/Admin-Sitzungen und einmalige OAuth-Prüfzustände dürfen nicht als erneut gültige Anmeldungen übernommen werden; sie sind in der Wiederherstellungsumgebung vor dem Start zu verwerfen. Das Verwerfen und erneute Anmelden ist Teil des manuellen Wiederherstellungsablaufs, nicht der hier angebotenen Nur-Lese-Prüfung.

`compose.production.yml` begrenzt Betriebs-/Fehlerlogs je App- und Proxy-Container mit `json-file`, `max-size: 10m` und `max-file: 3`. Das ist eine Größenrotation, **keine feste Tagesfrist**. Sie gilt nach Neuerstellung der Container. Die App-Zugriffslogs bleiben deaktiviert; Betriebs- und Fehlerausgaben sind weiterhin möglich. Host-/SSH-/Systemprotokolle und Protokolle des Hostinganbieters unterliegen eigenen, gesondert zu prüfenden Einstellungen.

Der Compose-Aufruf übergibt jetzt zusätzlich `--mail-key /app/data/mail-secrets.key`. Solange die erste Kontomail noch nicht erzeugt wurde, darf diese Datei fehlen, sofern die Datenbank keine verschlüsselten Mailinhalte enthält. Nach der ersten Mail muss der matching Schlüssel gesichert werden. `verify` entschlüsselt jede noch vorhandene Mailnutzlast zum Integritätsvergleich, ohne sie auszugeben.
