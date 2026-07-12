"""OpenAI GPT — Anbieter 2 (Textgenerierung + Embeddings für RAG)."""

from typing import Dict, List

from backend.config import get_settings
from backend.llm.base import LLMProvider, LLMResult


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        self.settings = get_settings()
        # Nutzer-Key (UI) hat Vorrang, sonst Fallback auf Server-/.env-Key.
        self._key = (api_key or "").strip() or self.settings.openai_api_key
        self._client = None

    def available(self) -> bool:
        return bool(self._key)

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._key)
        return self._client

    def generate(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2200,
        temperature: float = 0.4,
    ) -> LLMResult:
        full = [{"role": "system", "content": system}] + messages
        resp = self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=full,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return LLMResult(
            content=(resp.choices[0].message.content or "").strip(),
            provider=self.name,
            model=self.settings.openai_model,
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        resp = self.client.embeddings.create(
            model=self.settings.openai_embedding_model, input=texts
        )
        return [item.embedding for item in resp.data]
