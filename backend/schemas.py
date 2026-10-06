"""Pydantic-Schemas für Requests und Responses (strukturierte Validierung)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


# Account lifecycle payloads intentionally reject unused fields such as role/admin.
class AccountCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=12, max_length=128)

    def normalized_email(self):
        import re

        value = self.email.strip().lower()
        from fastapi import HTTPException

        try:
            local, domain = value.split("@")
            domain = domain.encode("idna").decode("ascii")
            if (
                not 1 <= len(local) <= 64 or local.startswith(".") or local.endswith(".")
                or ".." in local or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)
                or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+", domain)
                or len(local + "@" + domain) > 254
            ):
                raise ValueError("Email syntax")
        except (ValueError, UnicodeError):
            raise HTTPException(422, "E-Mail prüfen / check email") from None
        return local + "@" + domain


class AccountConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    terms_accepted: bool
    privacy_acknowledged: bool
    terms_version: str = Field(..., max_length=20)

    def validate_current(self):
        from fastapi import HTTPException

        from backend.account_terms import TERMS_VERSION

        if not self.terms_accepted or not self.privacy_acknowledged or self.terms_version != TERMS_VERSION:
            raise HTTPException(422, {
                "code": "TERMS_ACCEPTANCE_REQUIRED",
                "message": "Bitte die aktuellen AGB annehmen und die Datenschutzhinweise lesen.",
            })


class AccountRegistration(AccountCredentials, AccountConsent):
    display_name: str = Field("", max_length=200)
    language: str = Field("de", pattern="^(de|en|sq)$")


class AccountEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., min_length=3, max_length=254)
    language: str = Field("de", pattern="^(de|en|sq)$")

    def normalized_email(self):
        return AccountCredentials(email=self.email, password="validation-only-password").normalized_email()


class AccountTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(..., min_length=32, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class AccountResetRequest(AccountTokenRequest):
    password: str = Field(..., min_length=12, max_length=128)


class AccountPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email_notifications: bool = False


class AccountProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field("", max_length=200)
    first_name: str = Field("", max_length=100)
    last_name: str = Field("", max_length=100)
    phone: str = Field("", max_length=100)
    location: str = Field("", max_length=300)
    headline: str = Field("", max_length=300)
    language: str = Field("de", pattern="^(de|en|sq)$")
    preferences: AccountPreferences = Field(default_factory=AccountPreferences)


class AccountPasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=12, max_length=128)


class AccountEmailChange(AccountEmailRequest):
    current_password: str = Field(..., min_length=1, max_length=128)


class AccountDeletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(..., min_length=1, max_length=128)
    confirmation: str = Field(..., max_length=20)
