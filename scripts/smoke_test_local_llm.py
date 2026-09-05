"""Smoke-test the local OpenAI-compatible LLM endpoint.

Run from the repository root while the LM Studio/Bionic local server is active:

    python scripts/smoke_test_local_llm.py

This script validates connectivity only. It does not produce a recommender metric
and must not be treated as a Phase 2 paper-aligned experiment when an alternate
or derivative model is configured.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config


EXPECTED_TOKEN = "LOCAL_LLM_OK"


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test local LLM connectivity")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
        help="Path to local LLM TOML config",
    )
    args = parser.parse_args()

    config = load_local_llm_config(args.config)
    client = OpenAICompatibleLLMClient(
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
    )

    print("=" * 88)
    print("LOCAL LLM SMOKE TEST")
    print("=" * 88)
    print(f"Base URL         : {config.base_url}")
    print(f"Configured model : {config.model}")

    if "uncensored" in config.model.lower():
        print(
            "NOTE             : This derivative model is acceptable for connectivity testing only; "
            "Phase 2 paper-aligned results must use the exact Llama-3.2-3B-Instruct reference model."
        )

    print("\nChecking /models ...")
    models = client.list_models()
    if not models:
        raise RuntimeError("The local server responded, but no models were exposed by /v1/models")

    print(f"Models visible    : {len(models)}")
    for model_id in models:
        marker = "  <-- configured" if model_id == config.model else ""
        print(f"  - {model_id}{marker}")

    if config.model not in models:
        raise RuntimeError(
            f"Configured model `{config.model}` is not present in /v1/models. "
            "Update config/local_llm.toml or load the model in the local server."
        )

    print("\nSending minimal chat completion ...")
    started = time.perf_counter()
    response = client.chat_completion(
        model=config.model,
        messages=[
            {
                "role": "system",
                "content": "This is a connectivity test. Follow the user's formatting instruction exactly.",
            },
            {
                "role": "user",
                "content": f"Reply with exactly {EXPECTED_TOKEN} and nothing else.",
            },
        ],
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        seed=42,
    )
    elapsed = time.perf_counter() - started

    print(f"Response model    : {response.model or '<not reported>'}")
    print(f"Latency           : {elapsed:.3f} s")
    print(f"Response          : {response.content!r}")
    if response.usage:
        print(f"Usage             : {dict(response.usage)}")
    else:
        print("Usage             : <not reported by server>")

    normalized = response.content.strip()
    if normalized != EXPECTED_TOKEN:
        print("\nRESULT            : FAIL")
        print(
            "The endpoint works, but the model did not follow the exact smoke-test instruction. "
            "Send this output back so we can inspect model/runtime settings before Phase 2."
        )
        return 1

    print("\nRESULT            : PASS")
    print("Local Python -> OpenAI-compatible server -> model inference is working end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
