"""Pydantic-Schemas für Requests und Responses (strukturierte Validierung)."""

from typing import Literal

from pydantic import BaseModel, Field


class ApiKeys(BaseModel):
    """Vom Nutzer in der UI eingegebene API-Keys (überschreiben Server-Keys)."""

    openai: str | None = ""
    anthropic: str | None = ""
    gemini: str | None = ""
    grok: str | None = ""
    azure: str | None = ""


class SessionOut(BaseModel):
    session_id: str
    session_token: str = ""
    language: str
    has_cv: bool


class UploadOut(BaseModel):
    session_id: str
    filename: str
    characters: int
    chunks: int
    rag_mode: str  # "embeddings" | "tfidf"
    preview: str
    photo: str | None = None
    source_text: str = ""
    profile: dict = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    session_id: str
    job_description: str = Field(..., min_length=10, max_length=20000)
    wishes: str | None = Field("", max_length=4000)
    provider: Literal["claude", "openai", "gemini", "grok", "azure", "compare"] = "claude"
    language: Literal["de", "en", "sq"] = "de"
    technique: Literal["auto", "few_shot", "chain_of_thought"] = "auto"
    keys: ApiKeys | None = None
    model: str | None = Field(None, max_length=100)
    endpoint: str | None = Field(None, max_length=300)


class KeywordAnalysis(BaseModel):
    ats_score: float
    matched_keywords: list[str]
    missing_keywords: list[str]


class GenerationOut(BaseModel):
    generation_id: str
    provider: str
    model: str
    technique: str
    content: str
    analysis: KeywordAnalysis
    is_demo: bool = False


class GenerateResponse(BaseModel):
    mode: str  # "single" | "compare"
    results: list[GenerationOut]
    winner_provider: str | None = None
    recommendation: str | None = None


class RefineRequest(BaseModel):
    session_id: str
    instruction: str = Field(..., min_length=2, max_length=4000)
    current_content: str | None = Field(None, max_length=60000)
    provider: Literal["claude", "openai", "gemini", "grok", "azure"] = "claude"
    language: Literal["de", "en", "sq"] = "de"
    keys: ApiKeys | None = None
    model: str | None = Field(None, max_length=100)
    endpoint: str | None = Field(None, max_length=300)


class ExportRequest(BaseModel):
    session_id: str | None = None
    content: str = Field(..., min_length=10, max_length=60000)
    format: Literal["pdf", "docx"] = "pdf"
    design: Literal["modern", "classic", "minimal", "sapphire", "cobalt", "slate"] = "modern"
    language: Literal["de", "en", "sq"] = "de"
    filename: str | None = "Lebenslauf"
    photo: str | None = None  # data:image/...;base64,... oder leer/None


class StatusOut(BaseModel):
    app: str
    version: str
    providers: dict
    rag_mode: str
