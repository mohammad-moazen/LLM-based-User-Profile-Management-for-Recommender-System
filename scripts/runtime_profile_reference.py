"""Capture/compare a current-protocol runtime reference without touching frozen outputs.

Workflow
--------
1. With the baseline LM Studio loader profile (512/256/concurrency 1), run:

   python scripts/runtime_profile_reference.py capture --label baseline_512_256_1

   This replays 12 deterministic Review Extractor tasks using the *current final*
   prompt/schema/parser and stores their profile-safe outputs locally under
   ``outputs/runtime_profile_reference/``.

2. Change only the intended LM Studio loader parameters, then run:

   python scripts/runtime_profile_reference.py compare --label candidate_1024_512_1

   The candidate run is compared against the saved baseline reference using
   exact profile equality and field-aware lexical Jaccard, while also reporting
   latency, token usage, rejected-entry counts, and best-effort host RAM.

The script never modifies Phase 3 frozen outputs.
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

REFERENCE_DIR = REPO_ROOT / "outputs" / "runtime_profile_reference"
REFERENCE_PATH = REFERENCE_DIR / "current_protocol_reference.json"


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


def _profile_items(profile: object) -> set[str]:
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
    left_items = _profile_items(left)
    right_items = _profile_items(right)
    union = left_items | right_items
    if not union:
        return 1.0
    return len(left_items & right_items) / len(union)


def _sample_llama_server_memory() -> dict[str, Any] | None:
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
        commit_message=f"handoff: runtime profile {label}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def _run_current_protocol(
    *,
    selected_tasks: list[Any],
    phase3_config: Any,
    llm_config: Any,
    warmup: int,
) -> dict[str, object]:
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

    if warmup > 0:
        warmup_task = selected_tasks[0]
        for _ in range(warmup):
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
    total_tokens = 0
    total_rejected = 0

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
        usage = dict(response.usage) if response.usage else {}
        request_tokens = int(usage.get("total_tokens", 0) or 0)

        latencies.append(elapsed)
        total_tokens += request_tokens
        total_rejected += len(extraction.rejected_entries)
        rows.append(
            {
                "task_id": task.task_id,
                "profile": safe_profile,
                "latency_seconds": elapsed,
                "rejected_entry_count": len(extraction.rejected_entries),
                "total_tokens": request_tokens,
            }
        )
        print(
            f"[{ordinal:02d}/{len(selected_tasks):02d}] {task.task_id}  "
            f"latency={elapsed:.3f}s  rejected={len(extraction.rejected_entries)}"
        )

    memory_after = _sample_llama_server_memory()
    private_delta = None
    working_delta = None
    if memory_before is not None and memory_after is not None:
        private_delta = memory_after["private_gb"] - memory_before["private_gb"]
        working_delta = memory_after["working_set_gb"] - memory_before["working_set_gb"]

    return {
        "model": llm_config.model,
        "generation": {
            "temperature": phase3_config.generation.temperature,
            "max_tokens": phase3_config.generation.max_tokens,
            "seed": phase3_config.generation.seed,
            "structured_output": "evidence_backed_json_schema",
        },
        "sample_count": len(selected_tasks),
        "warmup_count": warmup,
        "mean_latency_seconds": statistics.mean(latencies),
        "median_latency_seconds": statistics.median(latencies),
        "min_latency_seconds": min(latencies),
        "max_latency_seconds": max(latencies),
        "total_reported_tokens": total_tokens,
        "rejected_entries": total_rejected,
        "memory": {
            "before": memory_before,
            "after": memory_after,
            "private_delta_gb": private_delta,
            "working_set_delta_gb": working_delta,
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture or compare a current-protocol runtime profile reference"
    )
    parser.add_argument("mode", choices=("capture", "compare"))
    parser.add_argument("--label", required=True)
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase3_review_extractor.toml"),
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
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

    print("=" * 96)
    print("CURRENT-PROTOCOL RUNTIME PROFILE REFERENCE")
    print("=" * 96)
    print(f"Mode                     : {args.mode}")
    print(f"Label                    : {args.label}")
    print(f"Model                    : {llm_config.model}")
    print(f"Samples                  : {len(selected_tasks)}")
    print(f"Warm-up                  : {args.warmup}")
    print("Frozen Phase 3 modified  : NO")
    print()

    current = _run_current_protocol(
        selected_tasks=selected_tasks,
        phase3_config=phase3_config,
        llm_config=llm_config,
        warmup=args.warmup,
    )

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode == "capture":
        payload = {
            "reference_label": args.label,
            "protocol": "current_final_review_extractor",
            "result": current,
        }
        REFERENCE_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        summary = {
            "experiment": "runtime_profile_reference_capture",
            "label": args.label,
            "reference_path": str(REFERENCE_PATH),
            "sample_count": current["sample_count"],
            "mean_latency_seconds": current["mean_latency_seconds"],
            "median_latency_seconds": current["median_latency_seconds"],
            "rejected_entries": current["rejected_entries"],
            "total_reported_tokens": current["total_reported_tokens"],
            "memory": current["memory"],
        }
        print()
        print("REFERENCE CAPTURED")
        print(f"mean latency      : {current['mean_latency_seconds']:.3f} sec")
        print(f"median latency    : {current['median_latency_seconds']:.3f} sec")
        print(f"reference         : {REFERENCE_PATH}")
        _publish(
            {
                "state": "RESULT",
                "experiment": "runtime_profile_reference_capture",
                "summary": summary,
            },
            args.label,
        )
        return 0

    if not REFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"Current-protocol reference does not exist: {REFERENCE_PATH}. "
            "Run capture mode under the baseline loader profile first."
        )

    reference_payload = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    reference_result = reference_payload.get("result")
    if not isinstance(reference_result, dict):
        raise ValueError("Reference file is missing a valid result object")
    reference_rows = reference_result.get("rows")
    current_rows = current.get("rows")
    if not isinstance(reference_rows, list) or not isinstance(current_rows, list):
        raise ValueError("Reference/current rows are invalid")

    reference_by_id = {
        str(row["task_id"]): row
        for row in reference_rows
        if isinstance(row, dict) and "task_id" in row
    }

    exact_matches = 0
    jaccards: list[float] = []
    compare_rows: list[dict[str, object]] = []
    for row in current_rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row["task_id"])
        if task_id not in reference_by_id:
            raise RuntimeError(f"Candidate task missing from reference: {task_id}")
        ref_row = reference_by_id[task_id]
        current_profile = row.get("profile")
        reference_profile = ref_row.get("profile")
        exact = current_profile == reference_profile
        jac = _jaccard(current_profile, reference_profile)
        exact_matches += int(exact)
        jaccards.append(jac)
        compare_rows.append(
            {
                "task_id": task_id,
                "exact_profile_match": exact,
                "jaccard": jac,
                "candidate_latency_seconds": row.get("latency_seconds"),
                "reference_latency_seconds": ref_row.get("latency_seconds"),
                "candidate_rejected_entry_count": row.get("rejected_entry_count"),
                "reference_rejected_entry_count": ref_row.get("rejected_entry_count"),
            }
        )

    ref_mean = float(reference_result.get("mean_latency_seconds", 0.0) or 0.0)
    candidate_mean = float(current.get("mean_latency_seconds", 0.0) or 0.0)
    speedup = ref_mean / candidate_mean if ref_mean > 0 and candidate_mean > 0 else None

    summary = {
        "experiment": "runtime_profile_reference_compare",
        "reference_label": reference_payload.get("reference_label"),
        "candidate_label": args.label,
        "sample_count": len(compare_rows),
        "exact_profile_matches": exact_matches,
        "exact_profile_match_rate": exact_matches / len(compare_rows),
        "mean_jaccard": statistics.mean(jaccards),
        "median_jaccard": statistics.median(jaccards),
        "min_jaccard": min(jaccards),
        "reference_mean_latency_seconds": ref_mean,
        "candidate_mean_latency_seconds": candidate_mean,
        "speedup_vs_reference": speedup,
        "candidate_rejected_entries": current.get("rejected_entries"),
        "reference_rejected_entries": reference_result.get("rejected_entries"),
        "candidate_total_reported_tokens": current.get("total_reported_tokens"),
        "reference_total_reported_tokens": reference_result.get("total_reported_tokens"),
        "candidate_memory": current.get("memory"),
    }

    report_path = REFERENCE_DIR / f"compare_{args.label}.json"
    report_path.write_text(
        json.dumps({"summary": summary, "rows": compare_rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("=" * 96)
    print("RUNTIME PROFILE COMPARISON")
    print("=" * 96)
    print(f"exact profile matches : {exact_matches}/{len(compare_rows)}")
    print(f"mean Jaccard          : {summary['mean_jaccard']:.3f}")
    print(f"reference mean        : {ref_mean:.3f} sec")
    print(f"candidate mean        : {candidate_mean:.3f} sec")
    if speedup is not None:
        print(f"speedup               : {speedup:.3f}x")
    print(f"report                : {report_path}")

    _publish(
        {
            "state": "RESULT",
            "experiment": "runtime_profile_reference_compare",
            "summary": summary,
            "rows": compare_rows,
        },
        args.label,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
