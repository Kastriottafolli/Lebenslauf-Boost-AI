"""Compatibility facade using the current Anthropic Messages API."""

from backend.config import get_settings
from backend.llm.http_provider import HTTPProvider


class AnthropicProvider(HTTPProvider):
    def __init__(self, api_key=None):
        settings = get_settings()
        super().__init__(
            "claude",
            (api_key or "").strip()
            or (settings.anthropic_api_key if settings.allow_server_keys else ""),
            settings.anthropic_model,
        )
