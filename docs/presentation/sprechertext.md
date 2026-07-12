# Sprechertext zur Projektpräsentation

Gesamtdauer: ungefähr 4 Minuten.

## Folie 1 – Lebenslauf Boost AI

Lebenslauf Boost AI ist eine Webanwendung, die einen bestehenden Lebenslauf
gezielt auf eine Stellenanzeige ausrichtet. Das Projekt kombiniert RAG, zwei
verschiedene KI-Anbieter, einen ATS-Keyword-Check und den Export als PDF oder
Word. Wichtig ist dabei die Faktentreue: Die KI darf ausschließlich Angaben
verwenden, die im hochgeladenen Lebenslauf nachweisbar enthalten sind.

## Folie 2 – Problem und Lösung

Ein allgemeiner Lebenslauf passt selten optimal zu jeder Stelle. Die manuelle
Anpassung kostet Zeit, während frei eingesetzte generative KI neue Fähigkeiten
oder Erfolge erfinden kann. Die Anwendung analysiert deshalb Lebenslauf und
Stellenanzeige gemeinsam. RAG liefert nur relevante, belegte Inhalte an das
Sprachmodell. Claude und OpenAI erzeugen vergleichbare Entwürfe, die anschließend
mit einem anwendungsspezifischen ATS-Score bewertet werden.

## Folie 3 – Workflow

Der Workflow besteht aus drei sichtbaren Schritten. Zuerst werden
Stellenbeschreibung, Wünsche und Lebenslauf eingegeben. Die App extrahiert Text
und optional das Bewerbungsfoto und baut einen RAG-Index auf. Danach werden ein
oder zwei KI-Entwürfe erzeugt, verglichen und über Conversation History weiter
verfeinert. Im letzten Schritt wird zwischen drei Designs sowie PDF und Word
gewählt. Die Vorschau zeigt das Ergebnis vor dem Download.

## Folie 4 – Architektur und Datenmodell

Das Frontend besteht aus Vanilla HTML, CSS und JavaScript. FastAPI übernimmt
REST-Endpunkte und Orchestrierung, während Pydantic alle Requests validiert.
Claude und OpenAI sind über eine gemeinsame Provider-Schicht gekapselt. Die
Fachlogik für Extraktion, RAG, Prompts und Export ist modular getrennt.
SQLite speichert Sitzungen, CV-Dokumente, Generierungen und Nachrichten.
Dadurch bleiben Versionshistorie und Gesprächskontext vollständig erhalten.

## Folie 5 – Ergebnis und Roadmap

Der MVP erfüllt die zentralen KI-Engineering-Anforderungen: zwei Text-APIs,
mehrere Prompt-Techniken, dynamische Kontextinjektion, RAG, Conversation
History, Vergleichsanalyse und persistente Datenhaltung. API-Schlüssel bleiben
nach dem BYOK-Prinzip im Browser. Als nächste Schritte sind PostgreSQL,
Alembic-Migrationen, Nutzerkonten, Versions-Rollback sowie Tests und Docker
vorgesehen. Das Ergebnis ist ein vollständiger End-to-End-Workflow von echten
Nutzerdaten bis zum professionell exportierbaren Lebenslauf.
