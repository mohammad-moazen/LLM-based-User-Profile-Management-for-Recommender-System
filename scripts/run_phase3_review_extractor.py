"""Run the PURE Review Extractor on reviews required by frozen Phase 1 sessions.

This stage does not compute recommendation NDCG. Its purpose is to validate the
first PURE component on real canonical reviews before profile updating and final
recommendation are introduced.

For a recommendation target at position t, only reviews from interactions before
t are eligible. Unique observed reviews are extracted once and later reused by
the evolving profile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase2 import load_histories, load_sessions
from pure_recommender.phase3 import build_required_extraction_tasks, load_phase3_config
from pure_recommender.pure import (
    build_review_extractor_messages,
    parse_review_extraction,
    review_extractor_response_format,
)


def _load_latest_results(path: Path) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    if not path.exists():
        return latest
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if isinstance(row, dict) and isinstance(row.get("task_id"), str):
                latest[row["task_id"]] = row
    return latest


def _append_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _format_values(values: list[str], limit: int = 3) -> str:
    if not values:
        return "[]"
    shown = values[:limit]
    suffix = " ..." if len(values) > limit else ""
    return "[" + "; ".join(shown) + "]" + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PURE Phase 3 Review Extractor")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase3_review_extractor.toml"),
        help="Path to Review Extractor TOML config",
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
        help="Path to local LLM TOML config",
    )
    args = parser.parse_args()

    config = load_phase3_config(args.config)
    llm_config = load_local_llm_config(args.llm_config)

    for label, path in (
        ("interactions", config.input.interactions_path),
        ("sessions", config.input.sessions_path),
    ):
        if not path.exists():
            raise FileNotFoundError(f"Frozen Phase 1 {label} artifact not found: {path}")

    print("Loading frozen Phase 1 artifacts...")
    histories = load_histories(config.input.interactions_path)
    sessions = load_sessions(config.input.sessions_path)
    all_tasks = build_required_extraction_tasks(histories, sessions)
    tasks = (
        all_tasks
        if config.experiment.max_extractions == 0
        else all_tasks[: config.experiment.max_extractions]
    )

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

    output_dir = config.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "extractions.jsonl"
    summary_path = output_dir / "summary.json"

    latest_results = _load_latest_results(results_path) if config.experiment.resume else {}
    completed_ok = {
        task_id
        for task_id, row in latest_results.items()
        if row.get("status") == "ok"
    }

    print("\n" + "=" * 88)
    print("PURE PHASE 3 — REVIEW EXTRACTOR")
    print("=" * 88)
    print(f"Model                    : {llm_config.model}")
    print(f"Endpoint                 : {llm_config.base_url}")
    print(f"Frozen sessions          : {len(sessions)}")
    print(f"Required unique reviews  : {len(all_tasks)}")
    print(f"Requested this run       : {len(tasks)}")
    print(f"Temperature              : {config.generation.temperature}")
    print(f"Max output tokens        : {config.generation.max_tokens}")
    print(f"Generation seed          : {config.generation.seed}")
    print("Structured output        : JSON Schema")
    print("Grounding validation     : verbatim review span")
    print(f"Resume                   : {config.experiment.resume}")
    if "uncensored" in llm_config.model.lower():
        print("Model alignment           : derivative local model; not exact paper checkpoint")

    response_format = review_extractor_response_format()

    for ordinal, task in enumerate(tasks, start=1):
        if task.task_id in completed_ok:
            print(f"[{ordinal:03d}/{len(tasks):03d}] {task.task_id}: already complete; skipping")
            continue

        interaction = task.interaction
        messages = build_review_extractor_messages(interaction)
        asin = str(interaction["asin"])
        title = str(interaction["title"])
        source_review = str(interaction["review_text"])

        print(
            f"[{ordinal:03d}/{len(tasks):03d}] {task.task_id}: "
            f"ASIN={asin}, title={title!r} ...",
            flush=True,
        )
        started = time.perf_counter()
        raw_content = ""
        try:
            response = client.chat_completion(
                model=llm_config.model,
                messages=messages,
                temperature=config.generation.temperature,
                max_tokens=config.generation.max_tokens,
                seed=config.generation.seed,
                response_format=response_format,
            )
            elapsed = time.perf_counter() - started
            raw_content = response.content
            extraction = parse_review_extraction(
                raw_content,
                source_review=source_review,
            )
            extraction_dict = extraction.to_dict()

            result: dict[str, object] = {
                "task_id": task.task_id,
                "user_id": task.user_id,
                "interaction_position": task.interaction_position,
                "asin": asin,
                "title": title,
                "rating": interaction.get("rating"),
                "timestamp": interaction.get("timestamp"),
                "status": "ok",
                "component": "Review Extractor",
                "model": llm_config.model,
                "grounding_validation": "verbatim_review_span",
                "extraction": extraction_dict,
                "latency_seconds": elapsed,
                "usage": dict(response.usage) if response.usage else None,
                "raw_response": raw_content,
            }
            _append_result(results_path, result)
            latest_results[task.task_id] = result
            completed_ok.add(task.task_id)

            print(f"    likes        : {_format_values(extraction_dict['likes'])}")
            print(f"    dislikes     : {_format_values(extraction_dict['dislikes'])}")
            print(f"    key_features : {_format_values(extraction_dict['key_features'])}")
            print(f"    latency      : {elapsed:.2f}s")
        except Exception as exc:
            elapsed = time.perf_counter() - started
            error_result: dict[str, object] = {
                "task_id": task.task_id,
                "user_id": task.user_id,
                "interaction_position": task.interaction_position,
                "asin": asin,
                "title": title,
                "status": "error",
                "component": "Review Extractor",
                "model": llm_config.model,
                "grounding_validation": "verbatim_review_span",
                "latency_seconds": elapsed,
                "error": str(exc),
                "raw_response": raw_content,
            }
            _append_result(results_path, error_result)
            latest_results[task.task_id] = error_result
            print(f"    ERROR: {exc}")
            if raw_content:
                preview = raw_content if len(raw_content) <= 3000 else raw_content[:3000] + "...<truncated>"
                print("    RAW MODEL RESPONSE:")
                for line in preview.splitlines() or [preview]:
                    print(f"      {line}")
            if config.experiment.fail_fast:
                raise

    requested_ids = [task.task_id for task in tasks]
    requested_results = [
        latest_results[task_id]
        for task_id in requested_ids
        if task_id in latest_results
    ]
    ok_results = [row for row in requested_results if row.get("status") == "ok"]
    error_results = [row for row in requested_results if row.get("status") != "ok"]

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    latencies: list[float] = []
    users: set[str] = set()
    extracted_counts = {"likes": 0, "dislikes": 0, "key_features": 0}

    for row in ok_results:
        users.add(str(row["user_id"]))
        latencies.append(float(row["latency_seconds"]))
        usage = row.get("usage")
        if isinstance(usage, dict):
            total_prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
            total_completion_tokens += int(usage.get("completion_tokens", 0) or 0)
            total_tokens += int(usage.get("total_tokens", 0) or 0)
        extraction = row.get("extraction")
        if isinstance(extraction, dict):
            for key in extracted_counts:
                value = extraction.get(key)
                if isinstance(value, list):
                    extracted_counts[key] += len(value)

    status = "PASS" if len(ok_results) == len(tasks) and not error_results else "INCOMPLETE"
    summary: dict[str, object] = {
        "component": "Review Extractor",
        "model": llm_config.model,
        "model_alignment": (
            "derivative_local_model_not_exact_paper_checkpoint"
            if "uncensored" in llm_config.model.lower()
            else "model_identifier_does_not_independently_prove_checkpoint_identity"
        ),
        "frozen_sessions": len(sessions),
        "required_unique_extractions": len(all_tasks),
        "requested_extractions": len(tasks),
        "successful_extractions": len(ok_results),
        "failed_extractions": len(error_results),
        "users_in_successful_extractions": len(users),
        "generation": {
            "temperature": config.generation.temperature,
            "max_tokens": config.generation.max_tokens,
            "seed": config.generation.seed,
            "structured_output": "json_schema",
            "grounding_validation": "verbatim_review_span",
        },
        "extracted_entry_counts": extracted_counts,
        "usage_totals": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
        },
        "latency": {
            "total_seconds": sum(latencies),
            "mean_seconds": (sum(latencies) / len(latencies) if latencies else 0.0),
        },
        "status": status,
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    print("\n" + "=" * 88)
    print("PHASE 3 REVIEW EXTRACTOR SUMMARY")
    print("=" * 88)
    print(f"required_unique_extractions : {len(all_tasks)}")
    print(f"requested_extractions       : {len(tasks)}")
    print(f"successful_extractions      : {len(ok_results)}")
    print(f"failed_extractions          : {len(error_results)}")
    print(f"users                       : {len(users)}")
    print(f"likes_entries               : {extracted_counts['likes']}")
    print(f"dislikes_entries            : {extracted_counts['dislikes']}")
    print(f"key_feature_entries         : {extracted_counts['key_features']}")
    print(f"total_tokens                : {total_tokens}")
    print(f"mean_latency_sec            : {summary['latency']['mean_seconds']:.3f}")
    print(f"status                      : {status}")
    print(f"results                     : {results_path}")
    print(f"summary                     : {summary_path}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
