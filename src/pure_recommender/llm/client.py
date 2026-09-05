"""Minimal OpenAI-compatible client for local LLM inference.

This module deliberately uses only the Python standard library. It keeps the
recommender independent from any specific local runtime while supporting the
OpenAI-compatible endpoints exposed by LM Studio/Bionic and other servers.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    model: str | None
    usage: Mapping[str, Any] | None
    raw: Mapping[str, Any]


class OpenAICompatibleLLMClient:
    """Small HTTP client for `/v1/models` and `/v1/chat/completions`."""

    def __init__(self, base_url: str, timeout_seconds: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request_json(
        self,
        method: str,
        endpoint: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        body = None
        headers = {"Accept": "application/json"}

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url=url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_bytes = response.read()
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Local LLM server returned HTTP {exc.code} for {url}: {error_body}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Could not connect to local LLM server at {url}: {exc.reason}"
            ) from exc

        try:
            decoded = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Local LLM server returned invalid JSON from {url}") from exc

        if not isinstance(decoded, dict):
            raise RuntimeError(f"Expected JSON object from {url}, got {type(decoded).__name__}")
        return decoded

    def list_models(self) -> list[str]:
        """Return model identifiers exposed by the local server."""

        payload = self._request_json("GET", "models")
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise RuntimeError("Unexpected /models response: `data` is not a list")

        model_ids: list[str] = []
        for row in data:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                model_ids.append(row["id"])
        return model_ids

    def chat_completion(
        self,
        *,
        model: str,
        messages: Sequence[Mapping[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 32,
        seed: int | None = None,
    ) -> LLMResponse:
        """Send one non-streaming chat-completion request."""

        request_payload: dict[str, Any] = {
            "model": model,
            "messages": [dict(message) for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if seed is not None:
            request_payload["seed"] = seed

        payload = self._request_json("POST", "chat/completions", request_payload)
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Unexpected chat-completion response: missing choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("Unexpected chat-completion response: invalid first choice")
        message = first_choice.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RuntimeError("Unexpected chat-completion response: missing message content")

        model_value = payload.get("model")
        usage_value = payload.get("usage")
        return LLMResponse(
            content=message["content"],
            model=model_value if isinstance(model_value, str) else None,
            usage=usage_value if isinstance(usage_value, dict) else None,
            raw=payload,
        )
