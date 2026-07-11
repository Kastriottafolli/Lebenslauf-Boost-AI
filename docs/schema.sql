-- ════════════════════════════════════════════════════════════════════════
--  Lebenslauf Boost AI — Datenbankschema (SQLite)
--  Entspricht app/models.py (SQLAlchemy erzeugt die Tabellen via create_all).
--  Ausführliche Doku: docs/DATABASE.md
-- ════════════════════════════════════════════════════════════════════════
PRAGMA foreign_keys = ON;   -- FK-Durchsetzung in SQLite aktivieren

-- ──────────────────────────────────────────────────────────────────────────
-- sessions — Nutzersitzung (zentraler Hub)
-- Eine Zeile pro Sitzung; klammert CV (1:1), Generierungen (1:n), Verlauf (1:n).
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE sessions (
    id              VARCHAR(36)  NOT NULL,                 -- UUIDv4 (nicht erratbar)
    language        VARCHAR(2)   NOT NULL DEFAULT 'de',    -- UI-/Ausgabesprache
    job_description TEXT         NOT NULL DEFAULT '',      -- eingefügte Stellenanzeige
    wishes          TEXT         NOT NULL DEFAULT '',      -- optionale Nutzerwünsche
    created_at      DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    PRIMARY KEY (id),
    CONSTRAINT ck_sessions_language CHECK (language IN ('de', 'en'))
);

-- ──────────────────────────────────────────────────────────────────────────
-- cv_documents — hochgeladener Lebenslauf + RAG-Index + Foto  (1:1 zur Sitzung)
-- UNIQUE(session_id) erzwingt die 1:1-Beziehung auf DB-Ebene;
-- erneuter Upload ersetzt die Zeile (DELETE + INSERT in /api/upload-cv).
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE cv_documents (
    id             VARCHAR(36)   NOT NULL,                 -- UUIDv4
    session_id     VARCHAR(36)   NOT NULL,                 -- → sessions.id
    filename       VARCHAR(255)  NOT NULL,                 -- Original-Dateiname
    content        TEXT          NOT NULL,                 -- extrahierter Volltext
    index_json     TEXT          NOT NULL,                 -- RAG-Index (JSON):
                                                           --   {"chunks":[…~700 Zeichen…],
                                                           --    "embeddings":[[1536 float]…] | null}
    photo_data_url TEXT,                                   -- "data:image/jpeg;base64,…" | NULL
    created_at     DATETIME      NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    PRIMARY KEY (id),
    UNIQUE (session_id),                                   -- erzwingt 1:1
    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ix_cv_documents_session_id ON cv_documents (session_id);

-- ──────────────────────────────────────────────────────────────────────────
-- generations — KI-erzeugte Lebenslauf-Versionen + Bewertung  (1:n)
-- /api/generate: 1 Zeile (einzeln) oder 2 Zeilen (Vergleich Claude vs. OpenAI);
-- /api/refine: +1 Zeile mit technique='refine'. Volle Versionshistorie.
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE generations (
    id               VARCHAR(36) NOT NULL,                 -- UUIDv4
    session_id       VARCHAR(36) NOT NULL,                 -- → sessions.id
    provider         VARCHAR(16) NOT NULL,                 -- Anbieter der Antwort
    model            VARCHAR(64) NOT NULL,                 -- z. B. 'gpt-4o-mini' | 'demo'
    technique        VARCHAR(24) NOT NULL,                 -- verwendete Prompt-Technik
    content          TEXT        NOT NULL,                 -- Lebenslauf als Markdown
    ats_score        FLOAT       NOT NULL DEFAULT 0.0,     -- Keyword-Abdeckung in %
    matched_keywords TEXT        NOT NULL DEFAULT '[]',    -- JSON-Array (lowercase)
    missing_keywords TEXT        NOT NULL DEFAULT '[]',    -- JSON-Array (lowercase)
    is_selected      BOOLEAN     NOT NULL DEFAULT 0,       -- reserviert (UI-Favorit)
    created_at       DATETIME    NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    PRIMARY KEY (id),
    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
    CONSTRAINT ck_generations_provider  CHECK (provider IN ('claude', 'openai')),
    CONSTRAINT ck_generations_technique CHECK
        (technique IN ('auto', 'few_shot', 'chain_of_thought', 'refine')),
    CONSTRAINT ck_generations_ats_range CHECK (ats_score >= 0.0 AND ats_score <= 100.0)
);
CREATE INDEX ix_generations_session_id ON generations (session_id);

-- ──────────────────────────────────────────────────────────────────────────
-- messages — Conversation History für iteratives Verfeinern  (1:n)
-- /api/generate speichert Prompt + gewählte Antwort; /api/refine liest die
-- letzte user/assistant-Runde und hängt Anweisung + neue Antwort an.
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE messages (
    id         VARCHAR(36) NOT NULL,                       -- UUIDv4
    session_id VARCHAR(36) NOT NULL,                       -- → sessions.id
    role       VARCHAR(9)  NOT NULL,                       -- wer spricht
    content    TEXT        NOT NULL,                       -- Prompt bzw. Antwort
    created_at DATETIME    NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    PRIMARY KEY (id),
    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
    CONSTRAINT ck_messages_role CHECK (role IN ('user', 'assistant'))
);
CREATE INDEX ix_messages_session_id ON messages (session_id);

-- ════════════════════════════════════════════════════════════════════════
--  Beispiel-Abfragen
-- ════════════════════════════════════════════════════════════════════════

-- Claude vs. OpenAI im direkten Vergleich (je Sitzung)
-- SELECT session_id,
--        MAX(CASE WHEN provider = 'claude' THEN ats_score END) AS claude,
--        MAX(CASE WHEN provider = 'openai' THEN ats_score END) AS openai
-- FROM generations
-- WHERE technique <> 'refine'
-- GROUP BY session_id;

-- Conversation History einer Sitzung, chronologisch
-- SELECT role, content, created_at
-- FROM messages WHERE session_id = :sid ORDER BY created_at;

-- Fehlende Keywords der letzten Generierung (SQLite-JSON)
-- SELECT j.value FROM generations g, json_each(g.missing_keywords) j
-- WHERE g.session_id = :sid ORDER BY g.created_at DESC LIMIT 12;
