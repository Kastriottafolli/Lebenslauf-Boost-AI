-- ════════════════════════════════════════════════════════════════════════
--  Lebenslauf Boost AI — Erweitertes Datenbankschema (PostgreSQL)
--  MVP (4 Tabellen, implementiert) + Roadmap (5 Tabellen, geplant)
--  Visuell: docs/schema-extended.svg · Interaktiv: canvases/datenbank-schema.canvas.tsx
-- ════════════════════════════════════════════════════════════════════════

-- Benötigt für gen_random_uuid(). In verwalteten PostgreSQL-Angeboten ist
-- pgcrypto meist bereits verfügbar; der Befehl ist idempotent.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Enums ────────────────────────────────────────────────────────────────

CREATE TYPE language_enum AS ENUM ('de', 'en');
CREATE TYPE provider_enum AS ENUM ('claude', 'openai');
CREATE TYPE technique_enum AS ENUM ('auto', 'few_shot', 'chain_of_thought', 'refine');
CREATE TYPE role_enum AS ENUM ('user', 'assistant');
CREATE TYPE plan_enum AS ENUM ('free', 'pro', 'team');
CREATE TYPE subscription_status_enum AS ENUM ('active', 'canceled', 'past_due', 'trialing');

-- ── Roadmap: Auth & Billing ─────────────────────────────────────────────

CREATE TABLE users (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(128),
    plan            plan_enum    NOT NULL DEFAULT 'free',
    email_verified  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

CREATE TABLE api_keys (
    id            VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id       VARCHAR(36)   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider      provider_enum NOT NULL,
    encrypted_key TEXT          NOT NULL,
    label         VARCHAR(64),
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_api_keys_user_id ON api_keys (user_id);

CREATE TABLE subscriptions (
    id                     VARCHAR(36)              PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id                VARCHAR(36)              NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_customer_id     VARCHAR(64)              NOT NULL UNIQUE,
    stripe_subscription_id VARCHAR(64),
    plan                   plan_enum                NOT NULL,
    status                 subscription_status_enum NOT NULL DEFAULT 'active',
    current_period_end     TIMESTAMPTZ,
    created_at             TIMESTAMPTZ              NOT NULL DEFAULT now()
);
CREATE INDEX ix_subscriptions_user_id ON subscriptions (user_id);

-- ── MVP: Sitzung & Hub ───────────────────────────────────────────────────

CREATE TABLE sessions (
    id              VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::text,
    language        language_enum NOT NULL DEFAULT 'de',
    job_description TEXT          NOT NULL DEFAULT '',
    wishes          TEXT          NOT NULL DEFAULT '',
    user_id         VARCHAR(36)   REFERENCES users(id) ON DELETE SET NULL,  -- Roadmap
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_sessions_user_id ON sessions (user_id);

CREATE TABLE cv_documents (
    id             VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id     VARCHAR(36)  NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
    filename       VARCHAR(255) NOT NULL,
    content        TEXT         NOT NULL,
    index_json     JSONB        NOT NULL,
    photo_data_url TEXT,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ix_cv_documents_session_id ON cv_documents (session_id);

-- ── MVP: KI-Ausgaben ──────────────────────────────────────────────────────

CREATE TABLE export_templates (
    id          VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    slug        VARCHAR(32) NOT NULL UNIQUE,
    name        VARCHAR(64) NOT NULL,
    config_json JSONB       NOT NULL,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE generations (
    id               VARCHAR(36)    PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id       VARCHAR(36)    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    provider         provider_enum  NOT NULL,
    model            VARCHAR(64)    NOT NULL,
    technique        technique_enum NOT NULL,
    content          TEXT           NOT NULL,
    ats_score        FLOAT          NOT NULL DEFAULT 0.0 CHECK (ats_score >= 0.0 AND ats_score <= 100.0),
    matched_keywords JSONB          NOT NULL DEFAULT '[]',
    missing_keywords JSONB          NOT NULL DEFAULT '[]',
    is_selected      BOOLEAN        NOT NULL DEFAULT FALSE,
    template_id      VARCHAR(36)    REFERENCES export_templates(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX ix_generations_session_id ON generations (session_id);

CREATE TABLE messages (
    id         VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id VARCHAR(36) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role       role_enum   NOT NULL,
    content    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_messages_session_id ON messages (session_id);

-- ── Roadmap: Erweiterte Inhalte ───────────────────────────────────────────

CREATE TABLE cover_letters (
    id         VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id VARCHAR(36)   NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    provider   provider_enum NOT NULL,
    content    TEXT          NOT NULL,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_cover_letters_session_id ON cover_letters (session_id);
