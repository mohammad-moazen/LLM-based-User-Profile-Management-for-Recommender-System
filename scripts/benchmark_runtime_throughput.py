"""Benchmark local LLM throughput without modifying frozen experiment outputs.

The benchmark replays a small deterministic sample of frozen Phase 3 Review
Extractor tasks using the exact same model, prompt, generation settings, JSON
schema, and grounding parser. It compares the newly produced profile-safe
extractions against the already frozen local Phase 3 outputs.

Use this script after changing only runtime/loader settings (for example LM
Studio evaluation or physical batch sizes). It never writes to the frozen Phase
3 result directory. A compact summary is published through handoff/latest.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

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


def _load_latest_results(path: Path) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    if not path.exists():
        raise FileNotFoundError(f"Frozen extractor results not found: {path}")
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


def _select_evenly_spaced(tasks: list[Any], count: int) -> list[Any]:
    if count <= 0:
        raise ValueError("--samples must be positive")
    if count >= len(tasks):
        return list(tasks)
    if count == 1:
        return [tasks[0]]

    indices: list[int] = []
    for i in range(count):
        index = round(i * (len(tasks) - 1) / (count - 1))
        if index not in indices:
            indices.append(index)
    return [tasks[index] for index in indices]


def _sample_llama_server_memory() -> dict[str, Any] | None:
    """Best-effort aggregate RAM sample for Windows llama-server processes."""

    powershell = r"""
$rows = @(Get-Process llama-server -ErrorAction SilentlyContinue |
    Select-Object Id, WorkingSet64, PrivateMemorySize64)
if ($rows.Count -eq 0) {
    Write-Output '[]'
} else {
    $rows | ConvertTo-Json -Compress
}
""".strip()

    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", powershell],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout.strip() or "[]")
    except Exception:
        return None

    rows = [payload] if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        return None

    working_set = sum(int(row.get("WorkingSet64", 0) or 0) for row in rows)
    private_bytes = sum(int(row.get("PrivateMemorySize64", 0) or 0) for row in rows)
    return {
        "process_count": len(rows),
        "working_set_gb": working_set / (1024 ** 3),
        "private_gb": private_bytes / (1024 ** 3),
    }


def _publish(payload: dict[str, object], label: str) -> None:
    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: runtime benchmark {label}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark local runtime throughput against frozen Review Extractor outputs"
    )
    parser.add_argument(
        "--label",
        default="current_runtime_profile",
        help="Short label describing the LM Studio runtime profile being tested",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=12,
        help="Number of frozen review-extraction tasks to replay",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=2,
        help="Warm-up requests before measured requests",
    )
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase3_review_extractor.toml"),
        help="Phase 3 config used only to locate frozen data/settings",
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
        help="Local LLM config",
    )
    args = parser.parse_args()

    if args.warmup < 0:
        raise ValueError("--warmup must be non-negative")

    phase3_config = load_phase3_config(args.config)
    llm_config = load_local_llm_config(args.llm_config)

    histories = load_histories(phase3_config.input.interactions_path)
    sessions = load_sessions(phase3_config.input.sessions_path)
    all_tasks = build_required_extraction_tasks(histories, sessions)
    selected_tasks = _select_evenly_spaced(all_tasks, args.samples)

    frozen_results_path = phase3_config.output.directory / "extractions.jsonl"
    frozen_latest = _load_latest_results(frozen_results_path)

    missing_or_bad = [
        task.task_id
        for task in selected_tasks
        if task.task_id not in frozen_latest or frozen_latest[task.task_id].get("status") != "ok"
    ]
    if missing_or_bad:
        raise RuntimeError(
            "Benchmark requires frozen successful Phase 3 results for every selected task; "
            f"missing_or_bad={missing_or_bad}"
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

    response_format = review_extractor_response_format()

    print("=" * 88)
    print("LOCAL RUNTIME THROUGHPUT BENCHMARK")
    print("=" * 88)
    print(f"Label                    : {args.label}")
    print(f"Model                    : {llm_config.model}")
    print(f"Endpoint                 : {llm_config.base_url}")
    print(f"Measured tasks           : {len(selected_tasks)}")
    print(f"Warm-up requests         : {args.warmup}")
    print(f"Temperature              : {phase3_config.generation.temperature}")
    print(f"Max output tokens        : {phase3_config.generation.max_tokens}")
    print(f"Generation seed          : {phase3_config.generation.seed}")
    print("Frozen outputs modified  : NO")
    print()

    warmup_task = selected_tasks[0]
    for _ in range(args.warmup):
        interaction = warmup_task.interaction
        response = client.chat_completion(
            model=llm_config.model,
            messages=build_review_extractor_messages(interaction),
            temperature=phase3_config.generation.temperature,
            max_tokens=phase3_config.generation.max_tokens,
            seed=phase3_config.generation.seed,
            response_format=response_format,
        )
        parse_review_extraction(
            response.content,
            source_review=str(interaction["review_text"]),
        )

    memory_before = _sample_llama_server_memory()

    rows: list[dict[str, object]] = []
    latencies: list[float] = []
    historical_latencies: list[float] = []
    total_tokens = 0
    exact_matches = 0

    for ordinal, task in enumerate(selected_tasks, start=1):
        interaction = task.interaction
        started = time.perf_counter()
        response = client.chat_completion(
            model=llm_config.model,
            messages=build_review_extractor_messages(interaction),
            temperature=phase3_config.generation.temperature,
            max_tokens=phase3_config.generation.max_tokens,
            seed=phase3_config.generation.seed,
            response_format=response_format,
        )
        elapsed = time.perf_counter() - started
        extraction = parse_review_extraction(
            response.content,
            source_review=str(interaction["review_text"]),
        )
        safe_extraction = extraction.to_profile_dict()
        frozen_row = frozen_latest[task.task_id]
        frozen_extraction = frozen_row.get("extraction")
        exact_match = safe_extraction == frozen_extraction
        exact_matches += int(exact_match)

        historical_latency = float(frozen_row.get("latency_seconds", 0.0) or 0.0)
        if historical_latency > 0:
            historical_latencies.append(historical_latency)

        usage = dict(response.usage) if response.usage else {}
        request_tokens = int(usage.get("total_tokens", 0) or 0)
        total_tokens += request_tokens
        latencies.append(elapsed)

        rows.append(
            {
                "task_id": task.task_id,
                "latency_seconds": elapsed,
                "historical_frozen_latency_seconds": historical_latency,
                "exact_profile_match": exact_match,
                "rejected_entry_count": len(extraction.rejected_entries),
                "total_tokens": request_tokens,
            }
        )
        print(
            f"[{ordinal:02d}/{len(selected_tasks):02d}] {task.task_id}  "
            f"latency={elapsed:.3f}s  exact_profile_match={exact_match}"
        )

    memory_after = _sample_llama_server_memory()

    mean_latency = statistics.mean(latencies)
    median_latency = statistics.median(latencies)
    historical_mean = (
        statistics.mean(historical_latencies) if historical_latencies else None
    )
    speedup_vs_historical = (
        historical_mean / mean_latency
        if historical_mean is not None and mean_latency > 0
        else None
    )

    memory_private_delta = None
    memory_working_delta = None
    if memory_before is not None and memory_after is not None:
        memory_private_delta = memory_after["private_gb"] - memory_before["private_gb"]
        memory_working_delta = (
            memory_after["working_set_gb"] - memory_before["working_set_gb"]
        )

    summary: dict[str, object] = {
        "experiment": "runtime_throughput_benchmark",
        "label": args.label,
        "model": llm_config.model,
        "sample_count": len(selected_tasks),
        "warmup_count": args.warmup,
        "generation": {
            "temperature": phase3_config.generation.temperature,
            "max_tokens": phase3_config.generation.max_tokens,
            "seed": phase3_config.generation.seed,
            "structured_output": "evidence_backed_json_schema",
        },
        "latency": {
            "mean_seconds": mean_latency,
            "median_seconds": median_latency,
            "min_seconds": min(latencies),
            "max_seconds": max(latencies),
            "historical_selected_mean_seconds": historical_mean,
            "speedup_vs_historical_selected": speedup_vs_historical,
        },
        "quality_guard": {
            "exact_profile_matches": exact_matches,
            "sample_count": len(selected_tasks),
            "exact_profile_match_rate": exact_matches / len(selected_tasks),
        },
        "total_reported_tokens": total_tokens,
        "memory": {
            "before": memory_before,
            "after": memory_after,
            "private_delta_gb": memory_private_delta,
            "working_set_delta_gb": memory_working_delta,
        },
    }

    report = {"summary": summary, "rows": rows}
    output_path = (
        REPO_ROOT
        / "outputs"
        / "runtime_throughput_benchmark"
        / f"{args.label}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print()
    print("=" * 88)
    print("RUNTIME THROUGHPUT SUMMARY")
    print("=" * 88)
    print(f"label                       : {args.label}")
    print(f"mean latency                : {mean_latency:.3f} sec")
    print(f"median latency              : {median_latency:.3f} sec")
    if historical_mean is not None:
        print(f"historical selected mean    : {historical_mean:.3f} sec")
        print(f"speedup vs historical       : {speedup_vs_historical:.3f}x")
    print(
        f"exact profile matches       : {exact_matches}/{len(selected_tasks)} "
        f"({100 * exact_matches / len(selected_tasks):.1f}%)"
    )
    if memory_private_delta is not None:
        print(f"private RAM delta           : {memory_private_delta:+.3f} GB")
        print(f"working-set RAM delta       : {memory_working_delta:+.3f} GB")
    print(f"local report                : {output_path}")

    _publish(
        {
            "state": "RESULT",
            "experiment": "runtime_throughput_benchmark",
            "summary": summary,
            "rows": rows,
        },
        args.label,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
