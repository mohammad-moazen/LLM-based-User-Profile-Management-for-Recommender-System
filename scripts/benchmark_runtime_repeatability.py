"""Measure same-profile run-to-run repeatability of the local Review Extractor.

Why this diagnostic exists
--------------------------
The first throughput baseline replayed 12 frozen Review Extractor tasks under the
*same* loader/model/generation profile that produced the accepted Phase 3 run,
but only 8/12 profile-safe extractions matched the historical outputs exactly.
That means exact-output equality is too brittle to use by itself when judging a
future loader change.

This script therefore keeps the LM Studio settings unchanged and replays the
same evenly spaced tasks several times in one process. It measures:

- latency distribution across repeated passes;
- exact profile equality against the frozen Phase 3 extraction;
- exact equality between repeated passes;
- deterministic lexical Jaccard overlap of profile-safe evidence sets;
- accepted/rejected entry counts;
- best-effort llama-server host RAM before/after the diagnostic.

The diagnostic never writes to the frozen Phase 3 output directory. Its local
report is written under ``outputs/runtime_repeatability/`` and a compact copy is
published through ``handoff/latest.json``.
"""

from __future__ import annotations

import argparse
from itertools import combinations
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
    """Load the latest stored row for each frozen Review Extractor task."""

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
    """Select deterministic tasks spanning the full required-extraction list."""

    if count <= 0:
        raise ValueError("--samples must be positive")
    if count >= len(tasks):
        return list(tasks)
    if count == 1:
        return [tasks[0]]

    indices: list[int] = []
    for index in range(count):
        selected = round(index * (len(tasks) - 1) / (count - 1))
        if selected not in indices:
            indices.append(selected)
    return [tasks[index] for index in indices]


def _sample_llama_server_memory() -> dict[str, Any] | None:
    """Best-effort aggregate host RAM for all Windows llama-server processes."""

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


def _profile_items(profile: object) -> set[str]:
    """Convert a profile dict into a field-aware lexical evidence set.

    Prefixing each evidence string with its category means the same review span
    occurring in different categories is treated as a different profile item.
    No semantic similarity or external model is introduced here.
    """

    items: set[str] = set()
    if not isinstance(profile, dict):
        return items

    for field_name in ("likes", "dislikes", "key_features"):
        values = profile.get(field_name)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str):
                normalized = " ".join(value.split()).casefold()
                if normalized:
                    items.add(f"{field_name}\u0000{normalized}")
    return items


def _jaccard(left: object, right: object) -> float:
    """Return deterministic Jaccard overlap between two profile-safe outputs."""

    left_items = _profile_items(left)
    right_items = _profile_items(right)
    union = left_items | right_items
    if not union:
        return 1.0
    return len(left_items & right_items) / len(union)


def _publish(payload: dict[str, object], label: str) -> None:
    """Publish only the compact benchmark handoff, leaving frozen outputs alone."""

    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: runtime repeatability {label}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure same-profile local LLM repeatability before runtime tuning"
    )
    parser.add_argument(
        "--label",
        default="baseline_repeatability_512_256_1",
        help="Short label for the unchanged LM Studio runtime profile",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=12,
        help="Number of evenly spaced frozen Review Extractor tasks per pass",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of measured passes over exactly the same selected tasks",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=2,
        help="Warm-up requests before the first measured pass",
    )
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase3_review_extractor.toml"),
        help="Phase 3 config used only to locate frozen artifacts/settings",
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
        help="Local LLM config",
    )
    args = parser.parse_args()

    if args.repeats < 2:
        raise ValueError("--repeats must be at least 2")
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
            "Repeatability benchmark requires frozen successful Phase 3 results; "
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

    print("=" * 96)
    print("LOCAL RUNTIME REPEATABILITY BENCHMARK")
    print("=" * 96)
    print(f"Label                    : {args.label}")
    print(f"Model                    : {llm_config.model}")
    print(f"Measured tasks/pass      : {len(selected_tasks)}")
    print(f"Measured repeats         : {args.repeats}")
    print(f"Warm-up requests         : {args.warmup}")
    print(f"Generation seed          : {phase3_config.generation.seed}")
    print("Runtime settings         : KEEP CURRENT LM STUDIO SETTINGS UNCHANGED")
    print("Frozen outputs modified  : NO")
    print()

    # Warm up the exact same inference path before the first measured pass. The
    # warm-up output is intentionally discarded and never compared to the frozen
    # scientific artifact.
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

    passes: list[dict[str, object]] = []
    profiles_by_task: dict[str, list[dict[str, list[str]]]] = {
        task.task_id: [] for task in selected_tasks
    }
    all_latencies: list[float] = []
    all_frozen_jaccards: list[float] = []

    for repeat_index in range(1, args.repeats + 1):
        print(f"--- measured pass {repeat_index}/{args.repeats} ---")
        pass_rows: list[dict[str, object]] = []
        pass_latencies: list[float] = []
        pass_exact_frozen = 0
        pass_frozen_jaccards: list[float] = []
        pass_rejected = 0
        pass_tokens = 0

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
            safe_profile = extraction.to_profile_dict()
            frozen_profile = frozen_latest[task.task_id].get("extraction")
            exact_frozen = safe_profile == frozen_profile
            frozen_jaccard = _jaccard(safe_profile, frozen_profile)

            usage = dict(response.usage) if response.usage else {}
            request_tokens = int(usage.get("total_tokens", 0) or 0)

            profiles_by_task[task.task_id].append(safe_profile)
            pass_latencies.append(elapsed)
            all_latencies.append(elapsed)
            pass_exact_frozen += int(exact_frozen)
            pass_frozen_jaccards.append(frozen_jaccard)
            all_frozen_jaccards.append(frozen_jaccard)
            pass_rejected += len(extraction.rejected_entries)
            pass_tokens += request_tokens

            pass_rows.append(
                {
                    "task_id": task.task_id,
                    "latency_seconds": elapsed,
                    "exact_match_vs_frozen": exact_frozen,
                    "jaccard_vs_frozen": frozen_jaccard,
                    "accepted_entry_count": sum(len(values) for values in safe_profile.values()),
                    "rejected_entry_count": len(extraction.rejected_entries),
                    "total_tokens": request_tokens,
                }
            )
            print(
                f"[{ordinal:02d}/{len(selected_tasks):02d}] {task.task_id}  "
                f"latency={elapsed:.3f}s  exact_frozen={exact_frozen}  "
                f"jaccard={frozen_jaccard:.3f}"
            )

        pass_summary = {
            "repeat": repeat_index,
            "mean_latency_seconds": statistics.mean(pass_latencies),
            "median_latency_seconds": statistics.median(pass_latencies),
            "exact_matches_vs_frozen": pass_exact_frozen,
            "exact_match_rate_vs_frozen": pass_exact_frozen / len(selected_tasks),
            "mean_jaccard_vs_frozen": statistics.mean(pass_frozen_jaccards),
            "median_jaccard_vs_frozen": statistics.median(pass_frozen_jaccards),
            "rejected_entries": pass_rejected,
            "total_reported_tokens": pass_tokens,
        }
        passes.append({"summary": pass_summary, "rows": pass_rows})
        print(
            f"pass {repeat_index} summary: mean={pass_summary['mean_latency_seconds']:.3f}s, "
            f"exact={pass_exact_frozen}/{len(selected_tasks)}, "
            f"mean_jaccard={pass_summary['mean_jaccard_vs_frozen']:.3f}"
        )
        print()

    memory_after = _sample_llama_server_memory()

    pair_exact_total = 0
    pair_comparison_total = 0
    pair_jaccards: list[float] = []
    per_task_repeatability: list[dict[str, object]] = []

    for task in selected_tasks:
        task_profiles = profiles_by_task[task.task_id]
        exact_pairs = 0
        task_pair_jaccards: list[float] = []
        for left_index, right_index in combinations(range(len(task_profiles)), 2):
            left_profile = task_profiles[left_index]
            right_profile = task_profiles[right_index]
            exact = left_profile == right_profile
            jaccard = _jaccard(left_profile, right_profile)
            exact_pairs += int(exact)
            pair_exact_total += int(exact)
            pair_comparison_total += 1
            task_pair_jaccards.append(jaccard)
            pair_jaccards.append(jaccard)

        unique_serialized = {
            json.dumps(profile, ensure_ascii=False, sort_keys=True)
            for profile in task_profiles
        }
        per_task_repeatability.append(
            {
                "task_id": task.task_id,
                "unique_profile_variants": len(unique_serialized),
                "exact_repeat_pairs": exact_pairs,
                "repeat_pair_count": len(task_pair_jaccards),
                "mean_pairwise_jaccard": (
                    statistics.mean(task_pair_jaccards) if task_pair_jaccards else 1.0
                ),
            }
        )

    private_delta = None
    working_delta = None
    if memory_before is not None and memory_after is not None:
        private_delta = memory_after["private_gb"] - memory_before["private_gb"]
        working_delta = memory_after["working_set_gb"] - memory_before["working_set_gb"]

    pass_means = [float(item["summary"]["mean_latency_seconds"]) for item in passes]
    summary: dict[str, object] = {
        "experiment": "runtime_repeatability_benchmark",
        "label": args.label,
        "model": llm_config.model,
        "sample_count": len(selected_tasks),
        "repeat_count": args.repeats,
        "measured_request_count": len(selected_tasks) * args.repeats,
        "warmup_count": args.warmup,
        "generation": {
            "temperature": phase3_config.generation.temperature,
            "max_tokens": phase3_config.generation.max_tokens,
            "seed": phase3_config.generation.seed,
            "structured_output": "evidence_backed_json_schema",
        },
        "latency": {
            "overall_mean_seconds": statistics.mean(all_latencies),
            "overall_median_seconds": statistics.median(all_latencies),
            "pass_mean_seconds": pass_means,
            "pass_mean_stddev_seconds": (
                statistics.stdev(pass_means) if len(pass_means) >= 2 else 0.0
            ),
        },
        "frozen_reference_similarity": {
            "mean_jaccard": statistics.mean(all_frozen_jaccards),
            "median_jaccard": statistics.median(all_frozen_jaccards),
            "min_jaccard": min(all_frozen_jaccards),
        },
        "same_profile_repeatability": {
            "exact_repeat_pairs": pair_exact_total,
            "repeat_pair_count": pair_comparison_total,
            "exact_repeat_pair_rate": (
                pair_exact_total / pair_comparison_total if pair_comparison_total else 1.0
            ),
            "mean_pairwise_jaccard": statistics.mean(pair_jaccards) if pair_jaccards else 1.0,
            "median_pairwise_jaccard": statistics.median(pair_jaccards) if pair_jaccards else 1.0,
            "min_pairwise_jaccard": min(pair_jaccards) if pair_jaccards else 1.0,
        },
        "memory": {
            "before": memory_before,
            "after": memory_after,
            "private_delta_gb": private_delta,
            "working_set_delta_gb": working_delta,
        },
    }

    report = {
        "summary": summary,
        "passes": passes,
        "per_task_repeatability": per_task_repeatability,
    }
    output_path = (
        REPO_ROOT
        / "outputs"
        / "runtime_repeatability"
        / f"{args.label}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 96)
    print("RUNTIME REPEATABILITY SUMMARY")
    print("=" * 96)
    print(f"overall mean latency          : {summary['latency']['overall_mean_seconds']:.3f} sec")
    print(f"pass mean latencies           : {[round(value, 3) for value in pass_means]}")
    print(f"mean Jaccard vs frozen        : {summary['frozen_reference_similarity']['mean_jaccard']:.3f}")
    print(
        "exact same-profile pairs      : "
        f"{pair_exact_total}/{pair_comparison_total} "
        f"({100 * summary['same_profile_repeatability']['exact_repeat_pair_rate']:.1f}%)"
    )
    print(
        "mean same-profile Jaccard     : "
        f"{summary['same_profile_repeatability']['mean_pairwise_jaccard']:.3f}"
    )
    if private_delta is not None:
        print(f"private RAM delta             : {private_delta:+.3f} GB")
        print(f"working-set RAM delta         : {working_delta:+.3f} GB")
    print(f"local report                  : {output_path}")

    _publish(
        {
            "state": "RESULT",
            "experiment": "runtime_repeatability_benchmark",
            "summary": summary,
            "pass_summaries": [item["summary"] for item in passes],
            "per_task_repeatability": per_task_repeatability,
        },
        args.label,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
