"""Gemeinsame Schnittstelle für alle LLM-Anbieter."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResult:
    content: str
    provider: str
    model: str


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 2200,
        temperature: float = 0.4,
    ) -> LLMResult: ...
