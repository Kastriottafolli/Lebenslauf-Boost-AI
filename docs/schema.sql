-- ════════════════════════════════════════════════════════════════
--  Lebenslauf Boost AI — Datenbankschema (SQLite)
--  Entspricht den SQLAlchemy-Modellen in app/models.py
-- ════════════════════════════════════════════════════════════════
PRAGMA foreign_keys = ON;

-- ── sessions ──────────────────────────────────────────────────────
-- Eine Nutzersitzung. Klammert Lebenslauf, Generierungen und Chat-Verlauf.
CREATE TABLE sessions (
    id              TEXT     PRIMARY KEY,           -- UUID
    language        TEXT     DEFAULT 'de',          -- 'de' | 'en'
    job_description TEXT     DEFAULT '',            -- eingefügte Stellenanzeige
    wishes          TEXT     DEFAULT '',            -- optionale Wünsche
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── cv_documents ──────────────────────────────────────────────────
-- Hochgeladener Lebenslauf + RAG-Index. 1:1 zur Sitzung.
CREATE TABLE cv_documents (
    id             TEXT     PRIMARY KEY,            -- UUID
    session_id     TEXT     REFERENCES sessions(id) ON DELETE CASCADE,
    filename       TEXT,
    content        TEXT,                            -- extrahierter Volltext
    index_json     TEXT,                            -- JSON: {chunks:[...], embeddings:[...]|null}
    photo_data_url TEXT,                            -- erkanntes Foto (data:image/jpeg;base64,...)
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── generations ───────────────────────────────────────────────────
-- Eine KI-generierte Lebenslauf-Version inkl. Bewertung. 1:n zur Sitzung.
CREATE TABLE generations (
    id               TEXT     PRIMARY KEY,          -- UUID
    session_id       TEXT     REFERENCES sessions(id) ON DELETE CASCADE,
    provider         TEXT,                          -- 'claude' | 'openai'
    model            TEXT,                          -- z. B. 'gpt-4o-mini'
    technique        TEXT,                          -- 'auto' | 'few_shot' | 'chain_of_thought' | 'refine'
    content          TEXT,                          -- Lebenslauf (Markdown)
    ats_score        REAL     DEFAULT 0.0,          -- 0–100 Keyword-Abdeckung
    matched_keywords TEXT     DEFAULT '[]',         -- JSON-Array
    missing_keywords TEXT     DEFAULT '[]',         -- JSON-Array
    is_selected      BOOLEAN  DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── messages ──────────────────────────────────────────────────────
-- Gesprächsverlauf für iteratives Verfeinern (Conversation History). 1:n.
CREATE TABLE messages (
    id         TEXT     PRIMARY KEY,                -- UUID
    session_id TEXT     REFERENCES sessions(id) ON DELETE CASCADE,
    role       TEXT,                                -- 'user' | 'assistant'
    content    TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Indizes für häufige Lookups (Fremdschlüssel) ──────────────────
CREATE INDEX idx_cv_session  ON cv_documents(session_id);
CREATE INDEX idx_gen_session ON generations(session_id);
CREATE INDEX idx_msg_session ON messages(session_id);
