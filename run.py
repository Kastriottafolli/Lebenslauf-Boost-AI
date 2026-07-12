"""Startet die App. In PyCharm: Rechtsklick auf diese Datei -> 'Run run'.

Danach im Browser öffnen:  http://localhost:8000
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
