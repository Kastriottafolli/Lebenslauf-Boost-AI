"""Zentrale Konfiguration, geladen aus .env (pydantic-settings)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Anthropic Claude (Anbieter 1) ──
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # ── OpenAI GPT (Anbieter 2) ──
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # ── App ──
    app_name: str = "Lebenslauf Boost AI"
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 10

    # ── RAG ──
    rag_chunk_size: int = 700
    rag_chunk_overlap: int = 120
    rag_top_k: int = 5

    @property
    def anthropic_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def any_provider_enabled(self) -> bool:
        return self.anthropic_enabled or self.openai_enabled


@lru_cache
def get_settings() -> Settings:
    return Settings()
