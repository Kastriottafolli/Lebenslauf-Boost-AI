"""SQLAlchemy-ORM-Modelle (SQLite)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Session(Base):
    """Eine Nutzersitzung — hält Lebenslauf, Generierungen und Chat-Verlauf zusammen."""

    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=_uuid)
    language = Column(String, default="de")
    job_description = Column(Text, default="")
    wishes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    cv = relationship(
        "CVDocument",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    generations = relationship(
        "Generation", back_populates="session", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan"
    )


class CVDocument(Base):
    """Hochgeladener Lebenslauf inkl. RAG-Index (Chunks + optionale Embeddings)."""

    __tablename__ = "cv_documents"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id"))
    filename = Column(String)
    content = Column(Text)
    index_json = Column(Text)  # JSON: {"chunks": [...], "embeddings": [...]|null}
    photo_data_url = Column(Text)  # aus dem CV extrahiertes Foto (data:image/jpeg;base64)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="cv")


class Generation(Base):
    """Eine vom Modell erzeugte Lebenslauf-Version inkl. Bewertung."""

    __tablename__ = "generations"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id"))
    provider = Column(String)
    model = Column(String)
    technique = Column(String)
    content = Column(Text)
    ats_score = Column(Float, default=0.0)
    matched_keywords = Column(Text, default="[]")  # JSON
    missing_keywords = Column(Text, default="[]")  # JSON
    is_selected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="generations")


class Message(Base):
    """Konversationsverlauf (Retaining Conversation History) für iteratives Verfeinern."""

    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id"))
    role = Column(String)  # user | assistant
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="messages")
