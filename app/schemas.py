"""Pydantic-Schemas für Requests und Responses (strukturierte Validierung)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ApiKeys(BaseModel):
    """Vom Nutzer in der UI eingegebene API-Keys (überschreiben Server-Keys)."""

    openai: Optional[str] = ""
    anthropic: Optional[str] = ""


class SessionOut(BaseModel):
    session_id: str
    language: str
    has_cv: bool


class UploadOut(BaseModel):
    session_id: str
    filename: str
    characters: int
    chunks: int
    rag_mode: str  # "embeddings" | "tfidf"
    preview: str
    photo: Optional[str] = None  # data:image/jpeg;base64,... (aus CV extrahiert)


class GenerateRequest(BaseModel):
    session_id: str
    job_description: str = Field(..., min_length=10)
    wishes: Optional[str] = ""
    provider: str = "claude"  # claude | openai | compare
    language: str = "de"
    technique: str = "auto"  # few_shot | chain_of_thought | auto
    keys: Optional[ApiKeys] = None


class KeywordAnalysis(BaseModel):
    ats_score: float
    matched_keywords: List[str]
    missing_keywords: List[str]


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
    results: List[GenerationOut]
    winner_provider: Optional[str] = None
    recommendation: Optional[str] = None


class RefineRequest(BaseModel):
    session_id: str
    instruction: str = Field(..., min_length=2)
    current_content: Optional[str] = None
    provider: str = "claude"  # claude | openai
    language: str = "de"
    keys: Optional[ApiKeys] = None


class ExportRequest(BaseModel):
    session_id: Optional[str] = None
    content: str = Field(..., min_length=10)
    format: str = "pdf"  # pdf | docx
    design: str = "modern"  # classic | modern | minimal
    language: str = "de"
    filename: Optional[str] = "Lebenslauf"
    photo: Optional[str] = None  # data:image/...;base64,... oder leer/None


class StatusOut(BaseModel):
    app: str
    version: str
    providers: dict
    rag_mode: str
