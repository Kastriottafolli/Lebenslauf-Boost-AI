# API-Kostenbeispiele · Stand 05.10.2026

Die App erstellt derzeit mit einem erfolgreichen KI-Aufruf die gesamte Mappe: Lebenslauf, Anschreiben, Motivation und E-Mail. Sie berechnet Keywords lokal; OCR, PDF und Word benötigen keine zusätzlichen KI-Tokens. Vergleiche und Nachbearbeitungen führen zu weiteren KI-Aufrufen.

Aktuelle Standardpreise im kurzen Kontext aus der [offiziellen OpenAI-Preisliste](https://developers.openai.com/api/docs/pricing), USD je eine Million Tokens:

| Modell | Eingabe | Ausgabe |
|---|---:|---:|
| GPT-6.1 Sol (aktueller Dokument-Standard) | 2,00 USD | 10,00 USD |
| GPT-6 Luna (Boosty-Themenerkennung) | 0,10 USD | 0,50 USD |

Rechenformel ohne Cache-Rabatte, Cache-Schreibkosten, Sondertarife und Tools: `(Input-Tokens × Inputpreis + Output-Tokens × Outputpreis) / 1.000.000`.

| Beispiel | Eingabe | Ausgabe | GPT-6.1 Sol | GPT-6 Luna |
|---|---:|---:|---:|---:|
| Mittlere vollständige Bewerbungsmappe | 8.000 | 4.000 | 0,056 USD | 0,0028 USD |
| Langer CV und umfangreiche Mappe | 20.000 | 8.000 | 0,12 USD | 0,006 USD |
| Boosty-Klassifikation, Beispiel | 600 | 20 | 0,0014 USD | 0,00007 USD |

Das sind **Rechenannahmen, keine gemessenen API-Läufe und keine festen Preise pro Lebenslauf**. Tatsächliche Tokenzahl hängt von CV, Stellenbeschreibung, Schreibvorgaben, JSON-Struktur, Sprache und Ausgabelänge ab. Bei Reasoning-Modellen können abgerechnete Reasoning-Tokens hinzukommen. Ein einzelner Lebenslauf wäre kürzer als die hier standardmäßig erzeugte vierteilige Mappe. GPT-6 Luna ist hier nur als Kostenvergleich genannt; Dokumentqualität wurde damit nicht live getestet.

8.000 Eingabe + 4.000 Ausgabe entsprechen bei GPT-6.1 Sol 5,6 US-Cent. 1.000 solche Mappen kosten rechnerisch 56 USD reine API-Nutzung. Bei 20.000 + 8.000 sind es 12 US-Cent bzw. 120 USD je 1.000 Mappen. Neue Versionen/Fehlversuche können die Nutzung erhöhen. Die separat eingesetzte Boosty-KI bezahlt nur die Hilfe, nicht diese Dokumentaufrufe.

Kein EUR-Betrag ohne aktuellen Abrechnungswechselkurs; Steuern, Hosting, Monitoring, Vertrags-/Regionalzuschläge, Zahlungsabwicklung und Support sind nicht enthalten. Die Preisliste nennt für regionale Verarbeitung einen Zuschlag von 10 % bei Modellen ab 05.03.2026. Erweitertes Caching oder andere Service-Tiers haben eigene Tarife. Vor echtem Betrieb Verbrauch anhand der Provider-Usage und Abrechnung messen; die Berechnung ist kein Ausgabenlimit.
