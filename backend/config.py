"""Zentrale Konfiguration, geladen aus .env (pydantic-settings)."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            os.environ.get(
                "TAFOLLIBOOST_SECRET_FILE", str(Path.home() / ".config/tafolliboost/secrets.env")
            ),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    # Dedicated help key: never read by CV/document providers.
    boosty_enabled: bool = False
    boosty_openai_api_key: str = ""
    boosty_openai_model: str = Field("gpt-6-luna", pattern=r"^[A-Za-z0-9._:-]{1,100}$")
    boosty_daily_limit: int = Field(500, ge=1, le=100000)
    boosty_session_daily_limit: int = Field(20, ge=1, le=200)
    allow_server_keys: bool = False
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000,capacitor://localhost,http://localhost,https://localhost"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    secure_cookies: bool = False
    retention_days: int = 30
    site_url: str = ""
    operator_name: str = "Kastriot Tafolli"
    operator_address: str = "Hauptstraße 1\n18609 Ostseebad Binz\nDeutschland"
    operator_email: str = "info@tafolli.net"

    # Hosted service: only server credentials and operator-selected models.
    hosted_ai_enabled: bool = True
    hosted_openai_model: str = "gpt-4.1-mini"
    hosted_help_model: str = "gpt-4.1-mini"
    ai_global_daily_calls: int = Field(300, ge=1, le=10000)
    ai_account_daily_packages: int = Field(3, ge=1, le=100)
    ai_account_daily_refines: int = Field(10, ge=1, le=100)
    ai_account_daily_help: int = Field(30, ge=1, le=200)
    ai_daily_budget_usd: float = Field(5.0, gt=0, le=1000)
    ai_input_usd_per_million: float = Field(0.4, ge=0)
    ai_output_usd_per_million: float = Field(1.6, ge=0)
    # Package credits apply independently of daily anti-abuse and spending limits.
    billing_free_packages: int = Field(3, ge=1, le=10)
    billing_single_cents: int = Field(199, ge=1, le=100000)
    billing_bundle10_cents: int = Field(999, ge=1, le=100000)
    billing_payments_enabled: bool = False
    billing_environment: str = Field("sandbox", pattern="^(sandbox|live)$")
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_merchant_id: str = ""
    oauth_base_url: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_apple_client_id: str = ""
    oauth_apple_client_secret: str = ""
    oauth_facebook_client_id: str = ""
    oauth_facebook_client_secret: str = ""
    oauth_x_client_id: str = ""
    oauth_x_client_secret: str = ""
    oauth_facebook_version: str = "v25.0"

    # ── App ──
    app_name: str = "tafolliboost.com"
    admin_key_file: str = "./data/admin-secrets.key"
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
