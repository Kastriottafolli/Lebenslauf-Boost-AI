"""Provider adapters using documented REST APIs; keys never enter logs/storage."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from backend.llm.base import LLMResult

REGISTRY = json.loads((Path(__file__).resolve().parents[2] / "static/providers.json").read_text())
PROVIDERS = {p["id"]: p for p in REGISTRY["providers"]}


def request_payload(name, key, system, messages, model=None, endpoint=None):
    config = PROVIDERS[name]
    model = model or config["default_model"]
    if not model or not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", model):
        raise HTTPException(422, "Modell/Deployment fehlt oder ist ungültig / invalid model.")
    url = config["endpoint"]
    headers = {"Content-Type": "application/json"}
    if name == "azure":
        parsed = urlparse(endpoint or "")
        if (
            parsed.scheme != "https"
            or not re.fullmatch(
                r"[a-z0-9-]+\.(openai\.azure\.com|cognitiveservices\.azure\.com)",
                parsed.hostname or "",
            )
            or parsed.port
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(422, "Azure-Endpunkt: https://RESOURCE.openai.azure.com")
        url = f"https://{parsed.hostname}/openai/v1/responses"
    if config["protocol"] == "messages":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        body = {
            "model": model,
            "max_tokens": 10000,
            "system": system,
            "messages": messages,
        }
    elif config["protocol"] == "gemini":
        headers["x-goog-api-key"] = key
        url += f"{model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "model" if m["role"] == "assistant" else "user",
                    "parts": [{"text": m["content"]}],
                }
                for m in messages
            ],
            "generationConfig": {"maxOutputTokens": 10000},
        }
    else:
        headers["Authorization"] = f"Bearer {key}"
        body = {
            "model": model,
            "input": [{"role": "system", "content": system}, *messages],
            "max_output_tokens": 10000,
            "store": False,
        }
    return url, headers, body


def response_text(name, data):
    if (
        data.get("status") == "incomplete"
        or data.get("stop_reason") == "max_tokens"
        or (data.get("candidates") or [{}])[0].get("finishReason") == "MAX_TOKENS"
    ):
        raise HTTPException(502, "KI-Ausgabe unvollständig / AI output incomplete.")
    if name == "claude":
        text = "\n".join(
            p.get("text", "") for p in data.get("content", []) if p.get("type") == "text"
        )
    elif name == "gemini":
        text = "\n".join(
            p.get("text", "")
            for p in (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            if not p.get("thought")
        )
    else:
        text = "\n".join(
            p.get("text", "")
            for item in data.get("output", [])
            if item.get("type") == "message"
            for p in item.get("content", [])
            if p.get("type") == "output_text"
        )
    if not text.strip() or len(text) > 100000:
        raise HTTPException(502, "Keine gültige KI-Ausgabe / no valid AI output.")
    return re.sub(r"^```(?:json|markdown)?\s*\n|\n```$", "", text.strip())


class HTTPProvider:
    def __init__(self, name, key="", model=None, endpoint=None):
        self.name, self.key, self.model, self.endpoint = name, key, model, endpoint

    def available(self):
        return bool(self.key.strip())

    def generate(self, system, messages, **kwargs):
        url, headers, body = request_payload(
            self.name, self.key, system, messages, self.model, self.endpoint
        )
        try:
            with httpx.Client(
                timeout=httpx.Timeout(120, connect=10),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.post(url, headers=headers, json=body)
            if response.status_code != 200:
                status = response.status_code
                explanation = (
                    "Key/Modellzugriff prüfen"
                    if status in (401, 403)
                    else "Guthaben/Limit prüfen"
                    if status == 429
                    else "Anbieter nicht verfügbar"
                )
                raise HTTPException(
                    502,
                    f"{self.name}: {status}. {explanation} / provider request failed.",
                )
            return LLMResult(
                response_text(self.name, response.json()),
                self.name,
                body.get("model", self.model or PROVIDERS[self.name]["default_model"]),
            )
        except (httpx.HTTPError, ValueError):
            raise HTTPException(
                502, "KI-Anbieter nicht erreichbar / AI provider unreachable."
            ) from None
