"""Run the accepted Phase 4 Profile Updater policy on every required prefix.

This is the thesis-grade full Profile Updater run. It consumes only the clean,
homogeneous Phase 3 Review Extractor artifact, groups the 134 required extraction
rows by user, applies the accepted v4 updater chronologically, and writes one
safe profile state after every observed interaction.

The full local artifact is intentionally not committed. Only a compact summary is
published through ``handoff/latest.json``. The resulting ``profile_states.jsonl``
is the source that the final PURE recommender will use: a recommendation target
at position t+1 may use only the profile state after interaction position t.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase4 import load_phase4_config
from pure_recommender.pure import (
    UserProfile,
    apply_retention_guard,
    build_profile_updater_messages,
    parse_profile_update,
    profile_updater_response_format,
)


PROFILE_FIELDS = ("likes", "dislikes", "key_features")
EXPERIMENT = "phase4_profile_updater_full_v4"


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _profile_counts(profile: UserProfile) -> dict[str, int]:
    counts = {field: len(getattr(profile, field)) for field in PROFILE_FIELDS}
    counts["total"] = sum(counts.values())
    return counts


def _mapping_entry_count(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    total = 0
    for field in PROFILE_FIELDS:
        entries = value.get(field)
        if isinstance(entries, list):
            total += len(entries)
    return total


def _finish_reason(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    value = choices[0].get("finish_reason")
    return value if isinstance(value, str) else None


def _load_extractions(path: Path) -> list[dict[str, object]]:
    """Load the latest successful row for every task and validate basic shape."""

    if not path.exists():
        raise FileNotFoundError(f"Final Review Extractor artifact not found: {path}")

    latest: dict[str, dict[str, object]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            task_id = row.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                raise ValueError(f"Missing task_id at {path}:{line_number}")
            latest[task_id] = row

    rows = [row for row in latest.values() if row.get("status") == "ok"]
    if len(rows) != len(latest):
        failed = sorted(
            str(row.get("task_id"))
            for row in latest.values()
            if row.get("status") != "ok"
        )
        raise RuntimeError(
            "Phase 3 source contains non-successful latest rows; refusing mixed input: "
            f"{failed[:10]}"
        )
    if not rows:
        raise RuntimeError("No successful Phase 3 extractions were found")
    return rows


def _group_and_validate_prefixes(
    rows: list[dict[str, object]],
) -> list[tuple[str, list[dict[str, object]]]]:
    """Return deterministic per-user chronological chains and enforce contiguity.

    A complete state cache must never skip an observed interaction within a user
    prefix. For each user we therefore require positions 1..max(position) with no
    gaps. This is a strong leakage/correctness invariant for downstream mapping.
    """

    by_user: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        user_id = row.get("user_id")
        position = row.get("interaction_position")
        extraction = row.get("extraction")
        if not isinstance(user_id, str) or not user_id:
            raise ValueError(f"Invalid user_id in extraction row: {row.get('task_id')}")
        try:
            position_int = int(position)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid interaction_position in {row.get('task_id')}") from exc
        if position_int < 1:
            raise ValueError(f"interaction_position must be >=1 in {row.get('task_id')}")
        if not isinstance(extraction, dict):
            raise ValueError(f"Invalid extraction object in {row.get('task_id')}")
        by_user[user_id].append(row)

    grouped: list[tuple[str, list[dict[str, object]]]] = []
    for user_id in sorted(by_user):
        user_rows = sorted(
            by_user[user_id],
            key=lambda row: (int(row["interaction_position"]), str(row["task_id"])),
        )
        positions = [int(row["interaction_position"]) for row in user_rows]
        expected = list(range(1, max(positions) + 1))
        if positions != expected:
            raise RuntimeError(
                f"Non-contiguous extraction prefix for user {user_id}: "
                f"positions={positions}, expected={expected}"
            )
        grouped.append((user_id, user_rows))
    return grouped


def _add_to_raw_unique_profile(
    current: dict[str, list[str]],
    extraction: dict[str, object],
) -> None:
    """Accumulate exact unique evidence for a no-updater entry-count reference."""

    for field in PROFILE_FIELDS:
        values = extraction.get(field)
        if not isinstance(values, list):
            raise ValueError(f"Extraction field {field!r} must be a list")
        seen = set(current[field])
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Extraction field {field!r} contains invalid text")
            clean = value.strip()
            if clean not in seen:
                current[field].append(clean)
                seen.add(clean)


def _raw_unique_count(current: dict[str, list[str]]) -> int:
    return sum(len(current[field]) for field in PROFILE_FIELDS)


def _publish(payload: dict[str, object], status_word: str) -> None:
    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: phase4 full profile updater {status_word.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full PURE Phase 4 Profile Updater v4")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase4_profile_updater_full.toml"),
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
    )
    args = parser.parse_args()

    config = load_phase4_config(args.config)
    llm_config = load_local_llm_config(args.llm_config)
    extraction_rows = _load_extractions(config.input.extractions_path)
    grouped = _group_and_validate_prefixes(extraction_rows)

    client = OpenAICompatibleLLMClient(
        base_url=llm_config.base_url,
        timeout_seconds=llm_config.timeout_seconds,
    )
    visible_models = client.list_models()
    if llm_config.model not in visible_models:
        raise RuntimeError(
            f"Configured model {llm_config.model!r} is not exposed by local server; "
            f"visible={visible_models}"
        )

    output_dir = config.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)
    states_path = output_dir / "profile_states.jsonl"
    summary_path = output_dir / "summary.json"
    if states_path.exists():
        states_path.unlink()

    expected_updates = len(extraction_rows)
    print("=" * 96)
    print("PURE PHASE 4 — FULL PROFILE UPDATER V4")
    print("=" * 96)
    print(f"Model                 : {llm_config.model}")
    print(f"Source extractions    : {config.input.extractions_path}")
    print(f"Users                 : {len(grouped)}")
    print(f"Expected updates      : {expected_updates}")
    print(f"Temperature           : {config.generation.temperature}")
    print(f"Max output tokens     : {config.generation.max_tokens}")
    print(f"Seed                  : {config.generation.seed}")
    print("Model output          : same-category entry IDs only")
    print("Safety guard          : information-preserving dominance guard v4")
    print()

    successful = 0
    failures: list[dict[str, object]] = []
    latencies: list[float] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    max_prompt_tokens = 0
    max_prompt_task_id: str | None = None
    total_guard_restored = 0
    total_guard_allowed_removals = 0
    cumulative_raw_unique_prefix_entries = 0
    cumulative_safe_prefix_entries = 0
    final_raw_unique_entries = 0
    final_safe_entries = 0

    for user_index, (user_id, user_rows) in enumerate(grouped, start=1):
        profile = UserProfile()
        raw_unique = {field: [] for field in PROFILE_FIELDS}
        print(f"USER {user_index}/{len(grouped)} {user_id} ({len(user_rows)} updates)")

        for row in user_rows:
            task_id = str(row["task_id"])
            position = int(row["interaction_position"])
            extraction_obj = row["extraction"]
            assert isinstance(extraction_obj, dict)

            _add_to_raw_unique_profile(raw_unique, extraction_obj)
            raw_prefix_count = _raw_unique_count(raw_unique)
            messages, concatenated, id_map = build_profile_updater_messages(profile, extraction_obj)
            response_format = profile_updater_response_format(id_map)
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
                model_selected = parse_profile_update(
                    raw_content,
                    allowed_profile=concatenated,
                    id_map=id_map,
                )
                updated, restored, allowed_removals = apply_retention_guard(
                    model_selected,
                    allowed_profile=concatenated,
                )

                usage = dict(response.usage) if response.usage else {}
                prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                completion_tokens = int(usage.get("completion_tokens", 0) or 0)
                request_tokens = int(usage.get("total_tokens", 0) or 0)
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                total_tokens += request_tokens
                if prompt_tokens > max_prompt_tokens:
                    max_prompt_tokens = prompt_tokens
                    max_prompt_task_id = task_id

                safe_count = _profile_counts(updated)["total"]
                restored_count = _mapping_entry_count(restored)
                removed_count = _mapping_entry_count(allowed_removals)
                total_guard_restored += restored_count
                total_guard_allowed_removals += removed_count
                cumulative_raw_unique_prefix_entries += raw_prefix_count
                cumulative_safe_prefix_entries += safe_count
                successful += 1
                latencies.append(elapsed)

                state_row: dict[str, object] = {
                    "status": "ok",
                    "task_id": task_id,
                    "user_id": user_id,
                    "interaction_position": position,
                    "source_extraction_task_id": task_id,
                    "profile": updated.to_dict(),
                    "counts": {
                        "raw_unique_prefix_entries": raw_prefix_count,
                        "concatenated_entries": _profile_counts(concatenated)["total"],
                        "model_selected_entries": _profile_counts(model_selected)["total"],
                        "safe_profile_entries": safe_count,
                        "guard_restored_entries": restored_count,
                        "guard_allowed_removals": removed_count,
                    },
                    "guard_restored_entries": restored,
                    "guard_allowed_removals": allowed_removals,
                    "finish_reason": _finish_reason(response.raw),
                    "latency_seconds": elapsed,
                    "usage": usage,
                }
                _append_jsonl(states_path, state_row)
                profile = updated

                print(
                    f"  {task_id}: raw_unique={raw_prefix_count} -> safe={safe_count}  "
                    f"restored={restored_count} removed={removed_count} "
                    f"prompt_tokens={prompt_tokens} latency={elapsed:.2f}s"
                )
            except Exception as exc:
                elapsed = time.perf_counter() - started
                failure = {
                    "task_id": task_id,
                    "user_id": user_id,
                    "interaction_position": position,
                    "error": str(exc),
                    "raw_response": raw_content,
                    "latency_seconds": elapsed,
                }
                failures.append(failure)
                _append_jsonl(states_path, {"status": "error", **failure})
                print(f"  {task_id}: ERROR: {exc}")
                if config.experiment.fail_fast:
                    break

        final_raw_unique_entries += _raw_unique_count(raw_unique)
        final_safe_entries += _profile_counts(profile)["total"]
        if failures and config.experiment.fail_fast:
            break

    status = "PASS" if successful == expected_updates and not failures else "INCOMPLETE"

    prefix_entry_compaction_ratio = (
        1.0 - (cumulative_safe_prefix_entries / cumulative_raw_unique_prefix_entries)
        if cumulative_raw_unique_prefix_entries
        else 0.0
    )
    final_entry_compaction_ratio = (
        1.0 - (final_safe_entries / final_raw_unique_entries)
        if final_raw_unique_entries
        else 0.0
    )

    summary: dict[str, object] = {
        "component": "Profile Updater",
        "run_version": "full_v4",
        "model": llm_config.model,
        "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
        "source_extractor_artifact": str(config.input.extractions_path),
        "users": len(grouped),
        "expected_updates": expected_updates,
        "successful_updates": successful,
        "failed_updates": len(failures),
        "prefix_contiguity_invariant": "PASS",
        "generation": {
            "temperature": config.generation.temperature,
            "max_tokens": config.generation.max_tokens,
            "seed": config.generation.seed,
            "structured_output": "dynamic_same_category_entry_id_schema",
        },
        "validation": "same_category_id_selection_plus_information_preserving_dominance_guard",
        "deletion_policy": "remove_only_exact_duplicates_or_overlaps_dominated_by_richer_same_category_evidence",
        "guard_totals": {
            "restored_entries": total_guard_restored,
            "allowed_removals": total_guard_allowed_removals,
        },
        "entry_compaction": {
            "cumulative_raw_unique_prefix_entries": cumulative_raw_unique_prefix_entries,
            "cumulative_safe_prefix_entries": cumulative_safe_prefix_entries,
            "prefix_entry_compaction_ratio": prefix_entry_compaction_ratio,
            "final_raw_unique_entries": final_raw_unique_entries,
            "final_safe_entries": final_safe_entries,
            "final_entry_compaction_ratio": final_entry_compaction_ratio,
            "note": "Entry-count compression is diagnostic only; recommender prompt-token compression is measured later.",
        },
        "usage_totals": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "max_prompt_tokens": max_prompt_tokens,
            "max_prompt_task_id": max_prompt_task_id,
        },
        "latency": {
            "total_seconds": sum(latencies),
            "mean_seconds": statistics.mean(latencies) if latencies else 0.0,
            "median_seconds": statistics.median(latencies) if latencies else 0.0,
        },
        "state_artifact": str(states_path),
        "status": status,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    handoff = {
        "state": "RESULT",
        "experiment": EXPERIMENT,
        "summary": summary,
        "errors": failures[:5],
    }
    _publish(handoff, status)

    print()
    print("=" * 96)
    print("FULL PROFILE UPDATER SUMMARY")
    print("=" * 96)
    print(f"successful_updates       : {successful}/{expected_updates}")
    print(f"failed_updates           : {len(failures)}")
    print(f"guard_restored_entries   : {total_guard_restored}")
    print(f"guard_allowed_removals   : {total_guard_allowed_removals}")
    print(f"prefix_entry_compaction  : {prefix_entry_compaction_ratio:.4f}")
    print(f"final_entry_compaction   : {final_entry_compaction_ratio:.4f}")
    print(f"max_prompt_tokens        : {max_prompt_tokens} ({max_prompt_task_id})")
    print(f"mean_latency_sec         : {summary['latency']['mean_seconds']:.3f}")
    print(f"status                   : {status}")
    print(f"profile_states           : {states_path}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
