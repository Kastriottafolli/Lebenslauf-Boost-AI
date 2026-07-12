"""Router-Schicht — dünne HTTP-Endpunkte, delegieren an die Services.

    system.py       GET  /api/status        Anbieter-/RAG-Status
    sessions.py     POST /api/session       neue Sitzung anlegen
    documents.py    POST /api/upload-cv     Lebenslauf hochladen (RAG-Index)
    generations.py  POST /api/generate      generieren (einzeln oder Vergleich)
                    POST /api/refine        iterativ verfeinern
    exports.py      POST /api/export        als PDF oder DOCX herunterladen
    frontend.py     GET  /                  Single-Page-Frontend ausliefern
"""

from backend.routers import documents, exports, frontend, generations, sessions, system

ALL_ROUTERS = [
    system.router,
    sessions.router,
    documents.router,
    generations.router,
    exports.router,
    frontend.router,
]
