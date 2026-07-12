"""Lebenslauf Boost AI — Backend (FastAPI).

Aufbau (Schichten-Architektur):

    backend/
    ├── main.py        App-Fabrik: erstellt die FastAPI-App, bindet Router + Frontend ein
    ├── config.py      Zentrale Konfiguration (.env)
    ├── database.py    SQLite/SQLAlchemy-Setup
    ├── models.py      ORM-Modelle (Tabellen)
    ├── schemas.py     Pydantic-Schemas (Request/Response-Validierung)
    ├── routers/       HTTP-Endpunkte — dünne Schicht, delegiert an Services
    ├── services/      Geschäftslogik (RAG, Extraktion, Generierung, Export …)
    └── llm/           KI-Anbieter (Claude, OpenAI) + Prompt-Verwaltung

Die Prompt-Texte selbst liegen als Vorlagen im Ordner  prompts/  (Projekt-Root).
"""

__version__ = "2.0.0"
