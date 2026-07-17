# Sprechertext zur Projektpräsentation

Gesamtdauer: ungefähr 4 Minuten.

## Folie 1 – Lebenslauf Boost AI

Lebenslauf Boost AI ist die aktuelle Webanwendung zur stellenbezogenen
Lebenslauf-Optimierung. Die Oberfläche im Sapphire-Nightfall-Design wird vom
Maskottchen Boosti begleitet. RAG, Claude und OpenAI, ATS-Keyword-Check sowie
sechs Export-Designs arbeiten ausschließlich mit belegten CV-Daten.

## Folie 2 – Problem und Lösung

Allgemeine Lebensläufe passen selten optimal zur Stelle. Manuelle Anpassung
kostet Zeit, frei eingesetzte generative KI kann Fakten erfinden. Die App
liefert deshalb nur relevante, belegte Abschnitte an das Modell, steuert die
Ausgabe mit professionellen Prompts und macht den Übergang mit einer
fünfsekündigen Ladesequenz nachvollziehbar.

## Folie 3 – Workflow

Drei UI-Schritte wie auf der Website: Eingabe mit Stellenanzeige, CV-Upload und
API-Key-Links; Bearbeiten mit Modellvergleich, ATS-Score und Refine; Design mit
sechs Vorlagen sowie PDF- oder Word-Download.

## Folie 4 – Architektur

Frontend, FastAPI-Backend, KI/RAG und SQLite sind klar getrennt. Keys folgen dem
BYOK-Prinzip und bleiben im Browser. Ohne Key läuft der Demo-Modus.

## Folie 5 – Ergebnis

Die aktuelle Website liefert einen vollständigen MVP: professionelles UI,
kontrollierte KI und exportierbare Ergebnisse. Als Nächstes stehen PostgreSQL,
Login, Rollback sowie Tests und Docker an.
