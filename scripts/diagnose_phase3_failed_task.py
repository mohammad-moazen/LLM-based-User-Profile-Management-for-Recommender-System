"""Diagnose one failed Phase 3 Review Extractor task without modifying experiment outputs.

This utility is intentionally read-only with respect to frozen/working Phase 3
artifacts. It replays exactly one selected task using the current final
prompt/schema/parser, reports the server finish reason and token usage, and
publishes the compact result through ``handoff/latest.json``.

The default task is the only failure from the first clean homogeneous final run.
Use ``--max-tokens 1024`` (the default here) to test whether the prior malformed
structured response was caused by the 512-token completion cap before changing
any scientific experiment configuration.
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

from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase2 import load_histories, load_sessions
from pure_recommender.phase3 import build_required_extraction_tasks, load_phase3_config
from pure_recommender.pure import (
    build_review_extractor_messages,
    parse_review_extraction,
    review_extractor_response_format,
)


def _finish_reason(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    value = first.get("finish_reason")
    return value if isinstance(value, str) else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose one Phase 3 Review Extractor failure without touching experiment outputs"
    )
    parser.add_argument(
        "--task-id",
        default="A2BFIYZYNK54QX:12",
        help="Exact Phase 3 extraction task id to replay",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Diagnostic completion-token cap; does not modify Phase 3 config",
    )
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase3_review_extractor.toml"),
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
    )
    args = parser.parse_args()

    if args.max_tokens < 1:
        raise ValueError("--max-tokens must be positive")

    phase3_config = load_phase3_config(args.config)
    llm_config = load_local_llm_config(args.llm_config)
    histories = load_histories(phase3_config.input.interactions_path)
    sessions = load_sessions(phase3_config.input.sessions_path)
    tasks = build_required_extraction_tasks(histories, sessions)
    task = next((row for row in tasks if row.task_id == args.task_id), None)
    if task is None:
        raise ValueError(f"Unknown Phase 3 task id: {args.task_id}")

    client = OpenAICompatibleLLMClient(
        base_url=llm_config.base_url,
        timeout_seconds=llm_config.timeout_seconds,
    )
    visible_models = client.list_models()
    if llm_config.model not in visible_models:
        raise RuntimeError(
            f"Configured model {llm_config.model!r} is not exposed by the local server. "
            f"Visible models: {visible_models}"
        )

    interaction = task.interaction
    source_review = str(interaction["review_text"])
    print("=" * 96)
    print("PHASE 3 FAILED-TASK DIAGNOSTIC")
    print("=" * 96)
    print(f"Task ID                  : {task.task_id}")
    print(f"Model                    : {llm_config.model}")
    print(f"Temperature              : {phase3_config.generation.temperature}")
    print(f"Seed                     : {phase3_config.generation.seed}")
    print(f"Diagnostic max tokens    : {args.max_tokens}")
    print("Experiment outputs       : NOT MODIFIED")
    print()

    started = time.perf_counter()
    response = client.chat_completion(
        model=llm_config.model,
        messages=build_review_extractor_messages(interaction),
        temperature=phase3_config.generation.temperature,
        max_tokens=args.max_tokens,
        seed=phase3_config.generation.seed,
        response_format=review_extractor_response_format(),
    )
    elapsed = time.perf_counter() - started
    finish_reason = _finish_reason(dict(response.raw))
    usage = dict(response.usage) if response.usage else None

    extraction = None
    error = None
    try:
        extraction = parse_review_extraction(
            response.content,
            source_review=source_review,
        )
    except Exception as exc:  # diagnostic must publish parser failure details
        error = str(exc)

    payload: dict[str, object] = {
        "state": "RESULT" if extraction is not None else "ERROR",
        "experiment": "phase3_failed_task_diagnostic",
        "task_id": task.task_id,
        "model": llm_config.model,
        "temperature": phase3_config.generation.temperature,
        "seed": phase3_config.generation.seed,
        "diagnostic_max_tokens": args.max_tokens,
        "finish_reason": finish_reason,
        "usage": usage,
        "latency_seconds": elapsed,
        "parse_status": "PASS" if extraction is not None else "FAIL",
        "error": error,
        "raw_response": response.content,
    }
    if extraction is not None:
        payload["extraction"] = extraction.to_profile_dict()
        payload["extraction_details"] = extraction.to_audit_dict()
        payload["rejected_entries"] = extraction.rejected_to_dict()

    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message="handoff: phase3 failed-task diagnostic",
        auto_push=True,
    )

    print(f"finish reason            : {finish_reason}")
    print(f"usage                    : {usage}")
    print(f"latency                  : {elapsed:.3f} sec")
    print(f"parse status             : {payload['parse_status']}")
    if error:
        print(f"error                    : {error}")
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")

    return 0 if extraction is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
