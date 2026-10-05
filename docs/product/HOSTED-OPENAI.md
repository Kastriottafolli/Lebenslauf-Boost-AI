# tafolliboost.com · zentraler OpenAI-Betrieb

Dieser Betriebsmodus ersetzt die frühere Gast-/BYOK-Oberfläche. Die bestehende Datenbank und Bewerbungen bleiben erhalten. Es ist keine Änderung der Kontopasswörter erforderlich.

## Ablauf

1. E-Mail-Konto erstellen oder anmelden. Bereits gültig angemeldete Nutzer gelangen direkt ins Studio.
2. Lebenslauf hochladen und erkannte Angaben bestätigen.
3. Stellenlink importieren oder Stellenbeschreibung einfügen, Sprache auswählen und OpenAI-Datenübermittlung bestätigen.
4. Alle vier generierten Dokumente prüfen, bearbeiten und als PDF, DOCX oder ZIP exportieren. Das Konto speichert Entwürfe, Designs und Bewerbungsverlauf.

Die UI zeigt den Dokumentablauf als vier Schritte: Profil → Stelle → Prüfen & erstellen → Mappe. Es gibt keinen Gasteditor, keine Nutzer-Key-Eingabe, keine Anbieter-/Modellauswahl und keinen kostenpflichtigen Anbieter-Vergleich. Das Beispiel lädt nur fiktive Eingaben; anschließend entsteht eine echte OpenAI-Mappe.

## Geheimnisse

Lokal liegt der Betreiber-Key in `~/.config/tafolliboost/secrets.env`, außerhalb des Repositorys, mit Dateirechten 0600. Settings lesen zuerst `.env`, dann diese private Datei. `TAFOLLIBOOST_SECRET_FILE` kann einen anderen privaten Pfad festlegen; normale Prozess-Umgebungsvariablen haben Vorrang. Weder HTML, JavaScript, öffentliche Konfiguration, Datenbank noch Git enthalten den Betreiber-Key. Schlüssel nicht in Chat, Quellcode oder Issues eintragen. Der bereits im Chat übermittelte Schlüssel sollte vor öffentlichem Betrieb im OpenAI-Dashboard ersetzt werden.

Für Produktion den Key über eine private Server-Umgebungsvariable oder eine nicht eingecheckte `.env` bereitstellen. Compose liest die private `.env`; die lokale Datei im Benutzerverzeichnis wird nicht in ein Docker-Image kopiert. Nach Geheimnisänderungen den Server neu starten. Niemals API-Schlüssel als Build-Argumente an das Frontend geben. Das Repository wurde durch diese Änderung nicht privat gestellt oder veröffentlicht.

## OpenAI und Kosten

Serverseitige Responses-API, `store=false`, feste Betreiber-Modelle und strukturierte JSON-Ausgabe für die vier Dokumente. Aktueller Standard: `gpt-4.1-mini`. Bei Modellwechsel die Preisparameter zusammen mit dem Modell anpassen. Boosty verwendet denselben Betreiber-Key, aber ausschließlich eine begrenzte Software-Themenerkennung; er erhält weder Lebenslauf noch Konto-/Chatverlauf und kann keine Daten verändern. Die angezeigten Antworten und Navigationsziele sind geprüft und fest vorgegeben.

Standardlimits pro Konto und UTC-Tag: 3 Mappen, 10 Überarbeitungen, 30 Hilfeanfragen. Insgesamt höchstens 300 KI-Aufrufe und 5 USD konservativ reserviertes Tagesbudget. Jede Anfrage reserviert vor dem Netzaufruf atomar einen Betrag anhand der Eingabegröße und maximalen Ausgabe. Fehlgeschlagene Aufrufe behalten ihre Reservation, damit Wiederholungen das Limit nicht umgehen. Globale Budgetzähler bleiben auch bei Kontolöschung bestehen. Nicht genutzte Ausgabetokens werden bei der Tageskapazität bewusst nicht freigegeben.

`ai_calls` speichert Status, Modell, Tokenzahlen und geschätzte Kosten, keine Prompts/Antworten. `ai_budgets` hält aggregierte Tagesdaten ohne Personenbezug. Beides wird nach 30 Tagen bereinigt; kontobezogene Aufrufe verschwinden bei Kontolöschung. Die Adminübersicht zeigt Tokenzahlen und die geschätzten USD-Kosten. Rechnungen, Steuern, Wechselkurse, Cachingrabatte und Hosting sind darin nicht enthalten. Keine Zahlung oder Werbeintegration wird ohne festgelegte Preise bzw. Anbieter aktiviert.

Gemessener lokaler Integrationstest am 05.10.2026, ausschließlich fiktive Beispieldaten:

| Vorgang | Eingabetokens | Ausgabetokens | Geschätzte USD |
|---|---:|---:|---:|
| Vier Bewerbungsdokumente | 924 | 869 | 0,001760 |
| Boosty-Softwarefrage | 296 | 6 | 0,000128 |

Preise: [offizielle Modellseite](https://developers.openai.com/api/docs/models/gpt-4.1-mini), 0,40 USD pro Million Eingabetokens und 1,60 USD pro Million Ausgabetokens. Lange Lebensläufe, längere Ausgaben und Überarbeitungen kosten entsprechend mehr. Die globalen Sicherheitsgrenzen ersetzen nicht die Limits des OpenAI-Projekts und die Überwachung seiner Rechnung.

## Social-Login

Google, Apple, Facebook und X sind serverseitig vorbereitet. Die Oberfläche zeigt nur konfigurierte Dienste als aktiv; ohne Entwickler-Zugangsdaten steht „bald verfügbar“. Der normale E-Mail-Login funktioniert bereits. Es wurde kein Konto bei einem externen Anmeldedienst für den Betreiber erstellt oder eine Genehmigung beantragt.

Alle Rücksprungadressen werden aus einem festen `OAUTH_BASE_URL` gebildet, zum Beispiel `https://tafolliboost.com`. Keine frei wählbaren Weiterleitungen. Je Anbieter die exakte Callback-URL beim Anbieter registrieren:

- Google: `https://tafolliboost.com/api/oauth/google/callback`
- Apple: `https://tafolliboost.com/api/oauth/apple/callback`
- Facebook: `https://tafolliboost.com/api/oauth/facebook/callback`
- X: `https://tafolliboost.com/api/oauth/x/callback`

Je Anbieter `OAUTH_<PROVIDER>_CLIENT_ID` und `OAUTH_<PROVIDER>_CLIENT_SECRET` privat auf dem Server setzen. Für Apple benötigt man eine Services-ID, Domainregistrierung und ein gültiges, zeitlich begrenztes signiertes Client-Secret aus dem Apple-Developer-Konto; Apple benötigt HTTPS und `form_post`. Bei Facebook die freigegebene Graph-Version über `OAUTH_FACEBOOK_VERSION` setzen. Anbieterfreigaben, Brandingvorgaben, mögliche Gebühren und echte externe Callback-Tests bleiben vor Aktivierung zu erledigen.

Einmaliger OAuth-State ist zehn Minuten gültig, an ein HttpOnly-Browsercookie gebunden und wird vor dem Tokenaustausch verbraucht. Google/X verwenden PKCE S256; Google/Apple Nonce. ID-Tokens werden auf RS256-Signatur, vertrauenswürdigen Aussteller, Audience, Ablauf, Nonce und bestätigte E-Mail geprüft. Facebook-Tokens werden gegen die App-ID geprüft; X liest die authentifizierte Identität aus `/2/users/me`. Anbieter-Subjects werden in `social_identities` gespeichert. E-Mail-Adressen führen niemals automatisch zu einer Verknüpfung mit bestehenden Konten; bei Kollision muss das bereits bestehende Konto genutzt werden. Ohne E-Mail verwenden X/Facebook eine interne Aliaskennung, keine erreichbare Adresse. Diese Konten werden über denselben sozialen Anbieter erneut geöffnet.

Instagram ist nicht als allgemeiner Website-Login eingebaut; die Instagram-Plattform richtet sich an Professional Accounts. Es gibt keinen vorgetäuschten Instagram-Login. Native Google-/Apple-Login-Flows in iOS/Android benötigen eine gesonderte Browser-/SDK-Anbindung; die synchronisierten Webressourcen sind kein Nachweis eines nativen Social-Logins.

Referenzen: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [Apple Tokenvalidierung](https://developer.apple.com/documentation/signinwithapplerestapi/generate-and-validate-tokens), [X OAuth/PKCE](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code), [Meta Login](https://developers.facebook.com/docs/facebook-login/manually-build-a-login-flow/).

## Schutz und Validierung

Der Hosted-Modus ist standardmäßig aktiv. Anonyme API-Aufrufe auf Import, Erzeugung, Export und Verlauf werden abgewiesen. Jede sitzungsbezogene Operation prüft zusätzlich den Kontobesitz; auch ein alter Sitzungstoken erlaubt einem anderen angemeldeten Konto keinen Zugriff. Nutzer dürfen weder Operator-Modell noch Anbieter oder Keys in Generierungsanfragen vorgeben. Alte `/api/generate`, `/api/refine` und `/api/provider/test` sind deaktiviert. Der bisherige Modus bleibt ausschließlich für Kompatibilitätstests über `HOSTED_AI_ENABLED=false` erhalten.

69 Backend- und 22 Frontend-Tests bestehen: Kontogrenzen, Credential-/Modell-Ausschluss, Quotas und Parallelzugriffe, kontounabhängiges Budget bei Löschung, OAuth-State-Bindung/Replay, Apple-POST-Callback und ID-Token-Signatur/Claims. Zwei echte OpenAI-Anfragen mit fiktiven Daten wurden erfolgreich im isolierten Previewkonto durchgeführt. Browserprüfung bestätigt vier Dokumente, Kontospeicherung und funktionierenden API-Chat. Produktivdomain, echte externe Social-Logins, Zahlungsabwicklung und App-Store-Veröffentlichung sind dadurch nicht erledigt. Der öffentliche Entwurfshinweis wurde auf Wunsch entfernt. Interne Freigabestatus und fehlende Betreiber-/Hostingangaben werden dadurch nicht automatisch bestätigt.
