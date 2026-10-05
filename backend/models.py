"""SQLAlchemy-ORM-Modelle (SQLite).

Schema-Grundsätze:
- Primärschlüssel sind UUIDv4-Strings (keine erratbaren, fortlaufenden IDs).
- Alle Fremdschlüssel sind NOT NULL + indiziert; `cv_documents.session_id`
  ist zusätzlich UNIQUE (erzwingt die 1:1-Beziehung auf DB-Ebene).
- Wertebereiche (language, provider, role, technique, ats_score) sind per
  CHECK-Constraint abgesichert — nicht nur per Konvention.
- Kaskadierendes Löschen läuft über die ORM-Beziehungen
  (cascade="all, delete-orphan"); die dokumentierte DDL in docs/schema.sql
  spiegelt dies als ON DELETE CASCADE.

Ausführliche Doku: docs/DATABASE.md
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Session(Base):
    """Nutzersitzung — der zentrale Hub.

    Klammert einen hochgeladenen Lebenslauf (1:1), alle KI-Generierungen (1:n)
    und den Konversationsverlauf (1:n) zusammen.
    """

    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("language IN ('de','en','sq')", name="ck_sessions_language"),)

    owner_token_hash = Column(String(64), nullable=True)
    owner_id = Column(String(36), nullable=True, index=True)
    id = Column(String(36), primary_key=True, default=_uuid)  # UUIDv4
    language = Column(String(2), nullable=False, default="de")  # 'de' | 'en'
    job_description = Column(Text, nullable=False, default="")  # eingefügte Stellenanzeige
    wishes = Column(Text, nullable=False, default="")  # optionale Nutzerwünsche
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    cv = relationship(
        "CVDocument",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    generations = relationship("Generation", back_populates="session", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class CVDocument(Base):
    """Hochgeladener Lebenslauf inkl. RAG-Index und erkanntem Bewerbungsfoto.

    Genau EIN Dokument pro Sitzung (UNIQUE session_id); ein erneuter Upload
    ersetzt den bestehenden Datensatz (delete + insert in /api/upload-cv).

    index_json — JSON-Objekt:
        {
          "chunks":     ["Absatz 1 …", "Absatz 2 …"],   # ~700 Zeichen, 120 Overlap
          "embeddings": [[0.0123, …], …] | null          # 1536-dim (text-embedding-3-small)
        }                                                # null => TF-IDF-Fallback (offline)

    photo_data_url — "data:image/jpeg;base64,…" (Portrait 4:5, max. 500 px) | NULL.
    """

    __tablename__ = "cv_documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # erzwingt 1:1
        index=True,
    )
    filename = Column(String(255), nullable=False)  # Original-Dateiname des Uploads
    content = Column(Text, nullable=False)  # extrahierter Volltext (PDF/DOCX/TXT)
    index_json = Column(Text, nullable=False)  # RAG-Index, Struktur siehe Docstring
    photo_data_url = Column(Text, nullable=True)  # erkanntes Foto oder NULL
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    session = relationship("Session", back_populates="cv")


class Generation(Base):
    """Eine KI-erzeugte Lebenslauf-Version inkl. Keyword-/ATS-Bewertung.

    Pro /api/generate entstehen 1 (Einzelmodus) oder 2 Zeilen (Vergleichsmodus:
    je eine für Claude und OpenAI); /api/refine ergänzt Zeilen mit technique='refine'.

    matched_keywords / missing_keywords — JSON-Array von Kleinbuchstaben-Begriffen,
    z. B. ["haccp", "menüplanung", "teamführung"].
    """

    __tablename__ = "generations_v2"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('claude','openai','gemini','grok','azure')",
            name="ck_generations_provider",
        ),
        CheckConstraint(
            "technique IN ('auto','few_shot','chain_of_thought','refine')",
            name="ck_generations_technique",
        ),
        CheckConstraint("ats_score >= 0.0 AND ats_score <= 100.0", name="ck_generations_ats_range"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(16), nullable=False)  # 'claude' | 'openai'
    model = Column(String(64), nullable=False)  # z. B. 'gpt-4o-mini' | 'demo'
    technique = Column(String(24), nullable=False)  # Prompt-Technik, s. CHECK
    content = Column(Text, nullable=False)  # Lebenslauf als Markdown
    ats_score = Column(Float, nullable=False, default=0.0)  # 0–100 % Keyword-Abdeckung
    matched_keywords = Column(Text, nullable=False, default="[]")  # JSON-Array
    missing_keywords = Column(Text, nullable=False, default="[]")  # JSON-Array
    is_selected = Column(Boolean, nullable=False, default=False)  # reserviert (UI-Auswahl)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    session = relationship("Session", back_populates="generations")


class Message(Base):
    """Konversationsverlauf (Retaining Conversation History).

    /api/generate speichert Prompt + gewählte Antwort, /api/refine liest die
    letzte user/assistant-Runde und hängt Anweisung + neue Antwort an — so
    behält das Modell den Kontext über mehrere Verfeinerungen hinweg.
    """

    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(9), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    session = relationship("Session", back_populates="messages")


class Account(Base):
    __tablename__ = "accounts"
    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    recovery_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class Login(Base):
    __tablename__ = "logins"
    token_hash = Column(String(64), primary_key=True)
    account_id = Column(
        String(36),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at = Column(DateTime, nullable=False)


class Application(Base):
    __tablename__ = "applications"
    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(200), nullable=False)
    status = Column(String(24), nullable=False, default="draft")
    data_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class AdminAccess(Base):
    __tablename__ = "admin_access"
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    secret_cipher = Column(Text, nullable=False)
    last_counter = Column(Integer, nullable=False, default=-1)
    setup_hash = Column(String(64), nullable=True, unique=True)
    setup_expires_at = Column(DateTime, nullable=True)


class AdminLogin(Base):
    __tablename__ = "admin_logins"
    token_hash = Column(String(64), primary_key=True)
    account_id = Column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at = Column(DateTime, nullable=False, index=True)


class Activity(Base):
    """Selected operation metadata only: never request bodies, keys or document text."""

    __tablename__ = "activity"
    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event = Column(String(64), nullable=False, index=True)
    outcome = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)


class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    day = Column(String(10), primary_key=True)
    page_views = Column(Integer, nullable=False, default=0)
    visits = Column(Integer, nullable=False, default=0)


class AdminAudit(Base):
    __tablename__ = "admin_audit"
    id = Column(String(36), primary_key=True, default=_uuid)
    admin_id = Column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action = Column(String(64), nullable=False)
    subject_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    id = Column(String(36), primary_key=True, default=_uuid)
    bucket = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
