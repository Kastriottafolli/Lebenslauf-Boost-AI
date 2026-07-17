# Sprechertext zur Projektpräsentation

Gesamtdauer: ungefähr 4 Minuten.

## Folie 1 – Lebenslauf Boost AI

Lebenslauf Boost AI ist eine Webanwendung, die einen bestehenden Lebenslauf
gezielt auf eine Stellenanzeige ausrichtet. Die Oberfläche im Sapphire-Nightfall-
Design wird vom Maskottchen Boosti begleitet. Das Projekt kombiniert RAG, zwei
KI-Anbieter, professionelle Prompt-Vorlagen, einen ATS-Keyword-Check und den
Export in sechs Designs als PDF oder Word. Wichtig ist die Faktentreue: Die KI
darf ausschließlich Angaben verwenden, die im hochgeladenen Lebenslauf
nachweisbar enthalten sind.

## Folie 2 – Problem und Lösung

Ein allgemeiner Lebenslauf passt selten optimal zu jeder Stelle. Die manuelle
Anpassung kostet Zeit, während frei eingesetzte generative KI neue Fähigkeiten
oder Erfolge erfinden kann. Die Anwendung analysiert deshalb Lebenslauf und
Stellenanzeige gemeinsam. RAG liefert nur relevante, belegte Inhalte an das
Sprachmodell. Professionelle Prompts steuern Claude und OpenAI. Ein ATS-Score
bewertet die Passung, und kurze Ladeübergänge machen den Seitenwechsel klar
nachvollziehbar.

## Folie 3 – Workflow

Der Workflow besteht aus drei sichtbaren Schritten. Zuerst werden
Stellenbeschreibung, Wünsche und Lebenslauf eingegeben. Direkte Links zu
Anthropic und OpenAI helfen beim Holen eines API-Keys; ohne Key läuft der
Demo-Modus. Danach erzeugt die App einen oder zwei KI-Entwürfe, vergleicht sie
und erlaubt Verfeinerungen über Conversation History. Im letzten Schritt stehen
sechs Designs sowie PDF und Word zur Auswahl.

## Folie 4 – Architektur und Datenmodell

Das Frontend besteht aus Vanilla HTML, CSS und JavaScript mit Boosti-Tour und
zweisprachiger Oberfläche. FastAPI übernimmt REST-Endpunkte und Orchestrierung,
während Pydantic alle Requests validiert. Claude und OpenAI sind über eine
gemeinsame Provider-Schicht gekapselt. Die Fachlogik für Extraktion, RAG,
Prompts und Export ist modular getrennt. SQLite speichert Sitzungen,
CV-Dokumente, Generierungen und Nachrichten.

## Folie 5 – Ergebnis und Roadmap

Der MVP erfüllt die zentralen KI-Engineering-Anforderungen: zwei Text-APIs,
professionelle Prompt-Techniken, dynamische Kontextinjektion, RAG, Conversation
History, Vergleichsanalyse und persistente Datenhaltung. API-Schlüssel bleiben
nach dem BYOK-Prinzip im Browser. Als nächste Schritte sind PostgreSQL,
Alembic-Migrationen, Nutzerkonten, Versions-Rollback sowie Tests und Docker
vorgesehen. Das Ergebnis ist ein vollständiger End-to-End-Workflow von echten
Nutzerdaten bis zum professionell exportierbaren Lebenslauf.
