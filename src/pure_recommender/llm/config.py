"""Configuration for a local OpenAI-compatible LLM server.

The configuration is intentionally independent from Phase 1 data settings so the
same recommender code can later switch between LM Studio/Bionic, vLLM, llama.cpp,
or another compatible local backend by changing configuration rather than model
logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class LocalLLMConfig:
    base_url: str
    model: str
    timeout_seconds: float = 120.0
    temperature: float = 0.0
    max_tokens: int = 32


def load_local_llm_config(config_path: str | Path) -> LocalLLMConfig:
    """Load local LLM configuration from a TOML file."""

    path = Path(config_path).resolve()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    server = raw.get("server", {})
    generation = raw.get("generation", {})

    base_url = str(server.get("base_url", "http://127.0.0.1:1234/v1")).rstrip("/")
    model = str(server.get("model", "")).strip()
    timeout_seconds = float(server.get("timeout_seconds", 120.0))
    temperature = float(generation.get("temperature", 0.0))
    max_tokens = int(generation.get("max_tokens", 32))

    if not model:
        raise ValueError("Local LLM config must specify server.model")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    if max_tokens < 1:
        raise ValueError("max_tokens must be >= 1")

    return LocalLLMConfig(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
    )
