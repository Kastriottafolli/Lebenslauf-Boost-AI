"""Zentrale Konfiguration, geladen aus .env (pydantic-settings)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Anthropic Claude (Anbieter 1) ──
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    # ── OpenAI GPT (Anbieter 2) ──
    openai_api_key: str = ""
    openai_model: str = "gpt-6.1-sol"
    openai_embedding_model: str = "text-embedding-3-small"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    grok_api_key: str = ""
    grok_model: str = "grok-4.7"
    azure_api_key: str = ""
    azure_model: str = ""
    azure_endpoint: str = ""
    allow_server_keys: bool = False
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000,capacitor://localhost,http://localhost,https://localhost"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    secure_cookies: bool = False
    retention_days: int = 30
    site_url: str = ""
    operator_name: str = "Kastriot Tafolli"
    operator_address: str = "Hauptstraße 1\n18609 Ostseebad Binz\nDeutschland"
    operator_email: str = "info@tafolli.net"

    # ── App ──
    app_name: str = "Candidaro"
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
