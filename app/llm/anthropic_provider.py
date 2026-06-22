"""Anthropic Claude — Anbieter 1."""

from typing import Dict, List

from ..config import get_settings
from .base import LLMProvider, LLMResult


class AnthropicProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str | None = None) -> None:
        self.settings = get_settings()
        # Nutzer-Key (UI) hat Vorrang, sonst Fallback auf Server-/.env-Key.
        self._key = (api_key or "").strip() or self.settings.anthropic_api_key
        self._client = None

    def available(self) -> bool:
        return bool(self._key)

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._key)
        return self._client

    def generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2200,
        temperature: float = 0.4,
    ) -> LLMResult:
        resp = self.client.messages.create(
            model=self.settings.anthropic_model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return LLMResult(
            content=text.strip(),
            provider=self.name,
            model=self.settings.anthropic_model,
        )
