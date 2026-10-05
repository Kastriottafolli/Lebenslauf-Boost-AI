"""Compatibility facade for Responses and optional embedding callers."""

import httpx

from backend.config import get_settings
from backend.llm.http_provider import HTTPProvider


class OpenAIProvider(HTTPProvider):
    def __init__(self, api_key=None):
        settings = get_settings()
        super().__init__(
            "openai",
            (api_key or "").strip()
            or (settings.openai_api_key if settings.allow_server_keys else ""),
            settings.openai_model,
        )

    def embed(self, texts):
        if not self.key:
            raise ValueError("OpenAI key required for embeddings")
        with httpx.Client(timeout=60, trust_env=False) as client:
            response = client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.key}"},
                json={"model": get_settings().openai_embedding_model, "input": texts},
            )
            response.raise_for_status()
            return [item["embedding"] for item in response.json()["data"]]
