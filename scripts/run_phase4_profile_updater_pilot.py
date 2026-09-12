"""Pilot PURE Profile Updater on clean final Review Extractor outputs.

The runner selects deterministic users with enough extracted interactions,
starts each user from an empty profile, and applies Profile Updater
chronologically. Pilot v2 uses a retention-biased deletion policy and publishes
exactly which input strings were removed at every update for qualitative audit.
Phase 3 artifacts remain untouched.
"""

from __future__ import annotations

import argparse
from collections import Counter
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
    build_profile_updater_messages,
    parse_profile_update,
    profile_updater_response_format,
)


PROFILE_FIELDS = ("likes", "dislikes", "key_features")


def _load_latest_successful_extractions(path: Path) -> list[dict[str, object]]:
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
            if isinstance(row, dict) and isinstance(row.get("task_id"), str):
                latest[str(row["task_id"])] = row

    successful = [row for row in latest.values() if row.get("status") == "ok"]
    if not successful:
        raise RuntimeError("No successful Review Extractor rows were found")
    return successful


def _select_pilot_users(
    rows: list[dict[str, object]],
    *,
    max_users: int,
    max_updates_per_user: int,
) -> list[tuple[str, list[dict[str, object]]]]:
    by_user: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        user_id = str(row.get("user_id", ""))
        if not user_id:
            continue
        by_user.setdefault(user_id, []).append(row)

    selected: list[tuple[str, list[dict[str, object]]]] = []
    for user_id in sorted(by_user):
        user_rows = sorted(
            by_user[user_id],
            key=lambda row: (int(row.get("interaction_position", 0) or 0), str(row.get("task_id", ""))),
        )
        if len(user_rows) < max_updates_per_user:
            continue
        selected.append((user_id, user_rows[:max_updates_per_user]))
        if len(selected) >= max_users:
            break

    if len(selected) < max_users:
        raise RuntimeError(
            "Not enough users have the requested number of chronological extractions: "
            f"needed_users={max_users}, updates_per_user={max_updates_per_user}"
        )
    return selected


def _profile_counts(profile: UserProfile) -> dict[str, int]:
    return {
        "likes": len(profile.likes),
        "dislikes": len(profile.dislikes),
        "key_features": len(profile.key_features),
        "total": len(profile.likes) + len(profile.dislikes) + len(profile.key_features),
    }


def _removed_entries(
    concatenated: UserProfile,
    updated: UserProfile,
) -> dict[str, list[str]]:
    """Return exact removed strings while preserving duplicate multiplicity/order."""

    removed: dict[str, list[str]] = {}
    for field_name in PROFILE_FIELDS:
        source_values = list(getattr(concatenated, field_name))
        retained_counts = Counter(getattr(updated, field_name))
        field_removed: list[str] = []
        for value in source_values:
            if retained_counts[value] > 0:
                retained_counts[value] -= 1
            else:
                field_removed.append(value)
        removed[field_name] = field_removed
    return removed


def _finish_reason(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    value = choices[0].get("finish_reason")
    return value if isinstance(value, str) else None


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _publish(payload: dict[str, object], status_word: str) -> None:
    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: phase4 profile updater pilot v2 {status_word.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PURE Phase 4 Profile Updater pilot v2")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase4_profile_updater_pilot.toml"),
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
    )
    args = parser.parse_args()

    config = load_phase4_config(args.config)
    llm_config = load_local_llm_config(args.llm_config)
    extraction_rows = _load_latest_successful_extractions(config.input.extractions_path)
    selected_users = _select_pilot_users(
        extraction_rows,
        max_users=config.experiment.max_users,
        max_updates_per_user=config.experiment.max_updates_per_user,
    )

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
    results_path = output_dir / "updates.jsonl"
    if results_path.exists():
        results_path.unlink()

    response_format = profile_updater_response_format()
    all_rows: list[dict[str, object]] = []
    latencies: list[float] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    failures: list[dict[str, object]] = []

    print("=" * 96)
    print("PURE PHASE 4 — PROFILE UPDATER PILOT V2")
    print("=" * 96)
    print(f"Model                 : {llm_config.model}")
    print(f"Extractor artifact    : {config.input.extractions_path}")
    print(f"Pilot users           : {config.experiment.max_users}")
    print(f"Updates/user          : {config.experiment.max_updates_per_user}")
    print(f"Temperature           : {config.generation.temperature}")
    print(f"Max output tokens     : {config.generation.max_tokens}")
    print(f"Seed                  : {config.generation.seed}")
    print("Subset validator      : exact same-category input strings only")
    print("Deletion policy       : retention-biased; remove only clear redundancy/overlap/conflict")
    print()

    final_profiles: dict[str, dict[str, list[str]]] = {}

    for user_id, user_rows in selected_users:
        profile = UserProfile()
        print(f"USER {user_id}")
        for update_index, extraction_row in enumerate(user_rows, start=1):
            extraction = extraction_row.get("extraction")
            if not isinstance(extraction, dict):
                raise ValueError(
                    f"Extractor row {extraction_row.get('task_id')} has invalid extraction object"
                )

            messages, concatenated = build_profile_updater_messages(profile, extraction)
            before_counts = _profile_counts(profile)
            concatenated_counts = _profile_counts(concatenated)
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
                updated = parse_profile_update(raw_content, allowed_profile=concatenated)
                after_counts = _profile_counts(updated)
                removed_entries = _removed_entries(concatenated, updated)

                usage = dict(response.usage) if response.usage else {}
                prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                completion_tokens = int(usage.get("completion_tokens", 0) or 0)
                request_tokens = int(usage.get("total_tokens", 0) or 0)
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                total_tokens += request_tokens
                latencies.append(elapsed)

                row: dict[str, object] = {
                    "status": "ok",
                    "user_id": user_id,
                    "update_index": update_index,
                    "source_task_id": extraction_row.get("task_id"),
                    "interaction_position": extraction_row.get("interaction_position"),
                    "previous_profile": profile.to_dict(),
                    "incoming_extraction": extraction,
                    "concatenated_profile": concatenated.to_dict(),
                    "updated_profile": updated.to_dict(),
                    "removed_entries": removed_entries,
                    "counts": {
                        "previous": before_counts,
                        "concatenated": concatenated_counts,
                        "updated": after_counts,
                        "removed_from_concatenated": (
                            concatenated_counts["total"] - after_counts["total"]
                        ),
                    },
                    "finish_reason": _finish_reason(response.raw),
                    "latency_seconds": elapsed,
                    "usage": usage,
                    "raw_response": raw_content,
                }
                _append_jsonl(results_path, row)
                all_rows.append(row)
                profile = updated

                print(
                    f"  update {update_index}: task={extraction_row.get('task_id')}  "
                    f"concat={concatenated_counts['total']} -> profile={after_counts['total']}  "
                    f"removed={row['counts']['removed_from_concatenated']}  "
                    f"latency={elapsed:.2f}s"
                )
                for field_name in PROFILE_FIELDS:
                    if removed_entries[field_name]:
                        print(f"    removed {field_name}: {removed_entries[field_name]}")
            except Exception as exc:
                elapsed = time.perf_counter() - started
                error_row: dict[str, object] = {
                    "status": "error",
                    "user_id": user_id,
                    "update_index": update_index,
                    "source_task_id": extraction_row.get("task_id"),
                    "interaction_position": extraction_row.get("interaction_position"),
                    "previous_profile": profile.to_dict(),
                    "incoming_extraction": extraction,
                    "concatenated_profile": concatenated.to_dict(),
                    "error": str(exc),
                    "raw_response": raw_content,
                    "latency_seconds": elapsed,
                }
                _append_jsonl(results_path, error_row)
                all_rows.append(error_row)
                failures.append(error_row)
                print(f"  update {update_index}: ERROR: {exc}")
                if config.experiment.fail_fast:
                    break

        final_profiles[user_id] = profile.to_dict()
        if failures and config.experiment.fail_fast:
            break

    successful_rows = [row for row in all_rows if row.get("status") == "ok"]
    expected_updates = config.experiment.max_users * config.experiment.max_updates_per_user
    status = "PASS" if len(successful_rows) == expected_updates and not failures else "INCOMPLETE"

    total_removed = sum(
        int(row.get("counts", {}).get("removed_from_concatenated", 0) or 0)
        for row in successful_rows
        if isinstance(row.get("counts"), dict)
    )

    summary: dict[str, object] = {
        "component": "Profile Updater",
        "pilot_version": "v2",
        "model": llm_config.model,
        "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
        "source_extractor_artifact": str(config.input.extractions_path),
        "selected_users": [user_id for user_id, _ in selected_users],
        "expected_updates": expected_updates,
        "successful_updates": len(successful_rows),
        "failed_updates": len(failures),
        "generation": {
            "temperature": config.generation.temperature,
            "max_tokens": config.generation.max_tokens,
            "seed": config.generation.seed,
            "structured_output": "three_category_subset_json_schema",
        },
        "validation": "exact_same_category_subset_no_new_text",
        "deletion_policy": "retain_unique_remove_only_clear_duplicate_overlap_or_conflict",
        "total_removed_entries_across_updates": total_removed,
        "usage_totals": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
        },
        "latency": {
            "total_seconds": sum(latencies),
            "mean_seconds": statistics.mean(latencies) if latencies else 0.0,
        },
        "final_profiles": final_profiles,
        "status": status,
    }

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    handoff_rows = [
        {
            "status": row.get("status"),
            "user_id": row.get("user_id"),
            "update_index": row.get("update_index"),
            "source_task_id": row.get("source_task_id"),
            "previous_profile": row.get("previous_profile"),
            "incoming_extraction": row.get("incoming_extraction"),
            "concatenated_profile": row.get("concatenated_profile"),
            "updated_profile": row.get("updated_profile"),
            "removed_entries": row.get("removed_entries"),
            "counts": row.get("counts"),
            "finish_reason": row.get("finish_reason"),
            "latency_seconds": row.get("latency_seconds"),
            "error": row.get("error"),
            "raw_response": row.get("raw_response") if row.get("status") != "ok" else None,
        }
        for row in all_rows
    ]

    _publish(
        {
            "state": "RESULT",
            "experiment": "phase4_profile_updater_pilot_v2",
            "summary": summary,
            "rows": handoff_rows,
        },
        status,
    )

    print()
    print("=" * 96)
    print("PROFILE UPDATER PILOT V2 SUMMARY")
    print("=" * 96)
    print(f"successful_updates : {len(successful_rows)}/{expected_updates}")
    print(f"failed_updates     : {len(failures)}")
    print(f"removed_entries    : {total_removed}")
    print(f"total_tokens       : {total_tokens}")
    print(f"mean_latency_sec   : {summary['latency']['mean_seconds']:.3f}")
    print(f"status             : {status}")
    print(f"results            : {results_path}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
