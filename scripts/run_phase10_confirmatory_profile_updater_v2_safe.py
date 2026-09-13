"""Run homogeneous Phase 10B2 v2 Profile Updater from scratch.

This runner does NOT reuse the 225 successful v1 states. Every confirmatory
profile update is generated under one uniform policy: the accepted Phase 4
prompt + guard, with exact repeated occurrences of the same valid selected ID
canonicalized to one occurrence before the original strict parser is applied.

No recommendation outcome is read or used here.
"""

from __future__ import annotations

from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import traceback
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis.hardware_preflight import verify_phase9_freeze
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase10_profile_canonical_v2 import (
    POLICY_NAME,
    duplicate_count,
    parse_profile_update_v2,
)
from pure_recommender.pure import (
    UserProfile,
    apply_retention_guard,
    build_profile_updater_messages,
    profile_from_mapping,
    profile_updater_response_format,
)

EXPERIMENT = "phase10_confirmatory_profile_updater_v2"
EXPECTED_USERS = 150
EXPECTED_SESSIONS = 767
EXPECTED_UPDATES = 1067
MAX_ATTEMPTS_PER_TASK = 3
COHORT_SHA256 = "72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca"
SESSIONS_SHA256 = "0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859"

COHORT_USERS_PATH = REPO_ROOT / "outputs/phase9_confirmatory_cohort_v1/cohort_users.json"
SESSIONS_PATH = REPO_ROOT / "outputs/phase9_confirmatory_cohort_v1/sessions.jsonl.gz"
COHORT_SUMMARY_PATH = REPO_ROOT / "outputs/phase9_confirmatory_cohort_v1/cohort_summary.json"
EXTRACTIONS_PATH = REPO_ROOT / "outputs/phase10_confirmatory_review_extractor_v1/extractions.jsonl"
EXTRACTOR_SUMMARY_PATH = REPO_ROOT / "outputs/phase10_confirmatory_review_extractor_v1/summary.json"
OUTPUT_DIR = REPO_ROOT / "outputs/phase10_confirmatory_profile_updater_v2"
STATES_PATH = OUTPUT_DIR / "profile_states.jsonl"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"


def _load_phase4_helpers() -> Any:
    path = REPO_ROOT / "scripts/run_phase4_profile_updater_full.py"
    spec = importlib.util.spec_from_file_location("phase4_helpers_v2", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load accepted Phase 4 helper functions")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return value


def _append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _load_v2_audit(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, int], int]:
    """Load only v2 rows; this prevents accidental mixing with the abandoned v1 run."""

    latest: dict[str, dict[str, object]] = {}
    attempts: dict[str, int] = {}
    rows_total = 0
    if not path.exists():
        return latest, attempts, rows_total

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows_total += 1
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError(f"Invalid v2 state row at line {line_number}")
            if row.get("policy") != POLICY_NAME:
                raise RuntimeError(
                    "Profile Updater v2 output contains a row from a different policy; "
                    "refusing mixed-protocol resume"
                )
            task_id = row.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                raise RuntimeError(f"Missing task_id in v2 state row at line {line_number}")
            latest[task_id] = row
            attempt = row.get("attempt_number")
            if isinstance(attempt, int) and attempt > 0:
                attempts[task_id] = max(attempts.get(task_id, 0), attempt)
    return latest, attempts, rows_total


def _preflight(phase4: Any) -> tuple[dict[str, object], list[tuple[str, list[dict[str, object]]]]]:
    freeze = verify_phase9_freeze(
        cohort_users_path=COHORT_USERS_PATH,
        sessions_path=SESSIONS_PATH,
        cohort_summary_path=COHORT_SUMMARY_PATH,
        expected_cohort_sha256=COHORT_SHA256,
        expected_sessions_sha256=SESSIONS_SHA256,
        expected_users=EXPECTED_USERS,
        expected_sessions=EXPECTED_SESSIONS,
    )

    extractor = _load_json(EXTRACTOR_SUMMARY_PATH)
    if extractor.get("status") != "PASS":
        raise RuntimeError("Phase 10B1 Review Extractor is not PASS")
    if int(extractor.get("successful_extractions", -1)) != EXPECTED_UPDATES:
        raise RuntimeError("Phase 10B1 successful extraction count mismatch")
    if int(extractor.get("failed_extractions", -1)) != 0:
        raise RuntimeError("Phase 10B1 contains failed source extractions")
    if int(extractor.get("users_in_successful_extractions", -1)) != EXPECTED_USERS:
        raise RuntimeError("Phase 10B1 user count mismatch")

    generation = extractor.get("generation")
    if not isinstance(generation, dict):
        raise RuntimeError("Phase 10B1 generation block missing")
    if generation.get("temperature") != 0.0 or generation.get("max_tokens") != 1024 or generation.get("seed") != 42:
        raise RuntimeError("Phase 10B1 generation settings do not match the frozen protocol")

    rows = phase4._load_extractions(EXTRACTIONS_PATH)
    grouped = phase4._group_and_validate_prefixes(rows)
    if len(rows) != EXPECTED_UPDATES or len(grouped) != EXPECTED_USERS:
        raise RuntimeError("Frozen confirmatory Profile Updater workload mismatch")
    return freeze, grouped


def _aggregate_latest(latest: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    ok_rows = [row for row in latest.values() if row.get("status") == "ok"]
    bad_rows = [row for row in latest.values() if row.get("status") != "ok"]
    prompt_tokens = completion_tokens = total_tokens = 0
    max_prompt_tokens = 0
    max_prompt_task_id: str | None = None
    latencies: list[float] = []
    restored = removed = 0
    canonicalized_responses = 0
    duplicate_occurrences_removed = 0

    for row in ok_rows:
        usage = row.get("usage")
        if isinstance(usage, Mapping):
            p = int(usage.get("prompt_tokens", 0) or 0)
            c = int(usage.get("completion_tokens", 0) or 0)
            t = int(usage.get("total_tokens", 0) or 0)
            prompt_tokens += p
            completion_tokens += c
            total_tokens += t
            if p > max_prompt_tokens:
                max_prompt_tokens = p
                max_prompt_task_id = str(row.get("task_id"))
        latency = row.get("latency_seconds")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))
        counts = row.get("counts")
        if isinstance(counts, Mapping):
            restored += int(counts.get("guard_restored_entries", 0) or 0)
            removed += int(counts.get("guard_allowed_removals", 0) or 0)
        dup = int(row.get("duplicate_id_occurrences_removed", 0) or 0)
        duplicate_occurrences_removed += dup
        if dup > 0:
            canonicalized_responses += 1

    return {
        "successful_updates": len(ok_rows),
        "failed_updates": len(bad_rows),
        "usage_totals": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "max_prompt_tokens": max_prompt_tokens,
            "max_prompt_task_id": max_prompt_task_id,
        },
        "guard_totals": {
            "restored_entries": restored,
            "allowed_removals": removed,
        },
        "canonicalization": {
            "policy": POLICY_NAME,
            "responses_with_exact_duplicate_ids": canonicalized_responses,
            "duplicate_id_occurrences_removed": duplicate_occurrences_removed,
            "semantic_note": "Repeated occurrences of the same valid selected ID are collapsed; no distinct ID is ignored or inferred.",
        },
        "latency": {
            "total_seconds": sum(latencies),
            "mean_seconds": statistics.mean(latencies) if latencies else 0.0,
            "median_seconds": statistics.median(latencies) if latencies else 0.0,
        },
    }


def _publish(payload: dict[str, object], message: str) -> None:
    ok, detail = publish_handoff(REPO_ROOT, payload, commit_message=message, auto_push=True)
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {detail}")


def main() -> int:
    try:
        phase4 = _load_phase4_helpers()
        freeze, grouped = _preflight(phase4)
        llm_cfg = load_local_llm_config(REPO_ROOT / "config/local_llm.toml")
        client = OpenAICompatibleLLMClient(
            base_url=llm_cfg.base_url,
            timeout_seconds=llm_cfg.timeout_seconds,
        )
        if llm_cfg.model not in client.list_models():
            raise RuntimeError(f"Configured model {llm_cfg.model!r} is not exposed by local server")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        latest, attempts, rows_at_start = _load_v2_audit(STATES_PATH)

        print("=" * 104)
        print("PHASE 10B2 v2 — HOMOGENEOUS CONFIRMATORY PROFILE UPDATER")
        print("=" * 104)
        print(f"Users                         : {EXPECTED_USERS}")
        print(f"Expected updates              : {EXPECTED_UPDATES}")
        print(f"Existing v2 successful states : {sum(r.get('status') == 'ok' for r in latest.values())}")
        print(f"Existing v2 audit rows         : {rows_at_start}")
        print(f"Policy                         : {POLICY_NAME}")
        print("Abandoned v1 states reused     : NO")
        print("Max Concurrent Predictions     : 1")
        print("Temperature / seed / max_tokens: 0.0 / 42 / 1024")
        print()

        unresolved: list[dict[str, object]] = []
        new_calls = 0
        new_successes = 0

        for user_index, (user_id, user_rows) in enumerate(grouped, start=1):
            profile = UserProfile()
            raw_unique = {field: [] for field in phase4.PROFILE_FIELDS}
            print(f"USER {user_index:03d}/{len(grouped):03d} {user_id}")

            for source_row in user_rows:
                task_id = str(source_row["task_id"])
                position = int(source_row["interaction_position"])
                extraction = source_row["extraction"]
                if not isinstance(extraction, dict):
                    raise RuntimeError(f"Invalid source extraction for {task_id}")

                phase4._add_to_raw_unique_profile(raw_unique, extraction)
                raw_prefix_count = phase4._raw_unique_count(raw_unique)

                existing = latest.get(task_id)
                if existing is not None and existing.get("status") == "ok":
                    if str(existing.get("user_id")) != user_id or int(existing.get("interaction_position", -1)) != position:
                        raise RuntimeError(f"Stored v2 state identity mismatch for {task_id}")
                    mapping = existing.get("profile")
                    if not isinstance(mapping, dict):
                        raise RuntimeError(f"Stored v2 profile invalid for {task_id}")
                    profile = profile_from_mapping(mapping)
                    continue

                used_attempts = attempts.get(task_id, 0)
                task_ok = False
                while used_attempts < MAX_ATTEMPTS_PER_TASK:
                    used_attempts += 1
                    attempts[task_id] = used_attempts
                    new_calls += 1
                    raw_content = ""
                    started = time.perf_counter()
                    try:
                        messages, concatenated, id_map = build_profile_updater_messages(profile, extraction)
                        response = client.chat_completion(
                            model=llm_cfg.model,
                            messages=messages,
                            temperature=0.0,
                            max_tokens=1024,
                            seed=42,
                            response_format=profile_updater_response_format(id_map),
                        )
                        elapsed = time.perf_counter() - started
                        raw_content = response.content
                        selected, duplicate_removed = parse_profile_update_v2(
                            raw_content,
                            allowed_profile=concatenated,
                            id_map=id_map,
                        )
                        updated, restored_entries, allowed_removals = apply_retention_guard(
                            selected,
                            allowed_profile=concatenated,
                        )
                        dup_total = duplicate_count(duplicate_removed)
                        state_row: dict[str, object] = {
                            "status": "ok",
                            "policy": POLICY_NAME,
                            "task_id": task_id,
                            "user_id": user_id,
                            "interaction_position": position,
                            "source_extraction_task_id": task_id,
                            "profile": updated.to_dict(),
                            "counts": {
                                "raw_unique_prefix_entries": raw_prefix_count,
                                "concatenated_entries": phase4._profile_counts(concatenated)["total"],
                                "model_selected_entries": phase4._profile_counts(selected)["total"],
                                "safe_profile_entries": phase4._profile_counts(updated)["total"],
                                "guard_restored_entries": phase4._mapping_entry_count(restored_entries),
                                "guard_allowed_removals": phase4._mapping_entry_count(allowed_removals),
                            },
                            "guard_restored_entries": restored_entries,
                            "guard_allowed_removals": allowed_removals,
                            "duplicate_ids_removed_by_field": duplicate_removed,
                            "duplicate_id_occurrences_removed": dup_total,
                            "finish_reason": phase4._finish_reason(response.raw),
                            "latency_seconds": elapsed,
                            "usage": dict(response.usage) if response.usage else {},
                            "attempt_number": used_attempts,
                        }
                        _append_jsonl(STATES_PATH, state_row)
                        latest[task_id] = state_row
                        profile = updated
                        new_successes += 1
                        task_ok = True
                        suffix = f" canonicalized_duplicates={dup_total}" if dup_total else ""
                        print(f"  {task_id}: OK attempt={used_attempts}{suffix}")
                        break
                    except Exception as exc:
                        elapsed = time.perf_counter() - started
                        error_row = {
                            "status": "error",
                            "policy": POLICY_NAME,
                            "task_id": task_id,
                            "user_id": user_id,
                            "interaction_position": position,
                            "error": str(exc),
                            "latency_seconds": elapsed,
                            "raw_response": raw_content,
                            "attempt_number": used_attempts,
                        }
                        _append_jsonl(STATES_PATH, error_row)
                        latest[task_id] = error_row
                        print(f"  {task_id}: ERROR attempt={used_attempts}: {exc}")

                if not task_ok:
                    unresolved.append({
                        "task_id": task_id,
                        "user_id": user_id,
                        "interaction_position": position,
                        "error": latest[task_id].get("error"),
                    })
                    break

            if unresolved:
                break

        aggregate = _aggregate_latest(latest)
        status = (
            "PASS"
            if aggregate["successful_updates"] == EXPECTED_UPDATES
            and aggregate["failed_updates"] == 0
            else "INCOMPLETE"
        )
        summary: dict[str, object] = {
            "component": "Profile Updater",
            "run_version": "confirmatory_homogeneous_v2",
            "status": status,
            "model": llm_cfg.model,
            "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
            "users": EXPECTED_USERS,
            "expected_updates": EXPECTED_UPDATES,
            **aggregate,
            "generation": {"temperature": 0.0, "max_tokens": 1024, "seed": 42},
            "runtime_max_concurrent_predictions": 1,
            "validation": "exact_duplicate_id_canonicalization_then_strict_parser_plus_information_preserving_guard_v4",
            "retry_policy": {
                "max_attempts_per_task": MAX_ATTEMPTS_PER_TASK,
                "no_semantic_response_repair": True,
            },
            "homogeneity": {
                "v1_states_reused": False,
                "all_1067_states_must_use_same_v2_policy": True,
                "introduced_before_confirmatory_recommendation_outcomes": True,
            },
            "resume": {
                "enabled": True,
                "new_llm_calls_this_invocation": new_calls,
                "new_successes_this_invocation": new_successes,
            },
            "phase9_freeze": freeze,
            "state_artifact": str(STATES_PATH),
        }
        SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

        payload = {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "confirmatory_recommendation_outcomes_inspected": False,
            "summary": summary,
            "unresolved": unresolved,
        }
        _publish(payload, "handoff: phase10 Profile Updater v2 " + ("pass" if status == "PASS" else "incomplete"))
        return 0 if status == "PASS" else 1

    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "confirmatory_recommendation_outcomes_inspected": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        _publish(payload, "handoff: phase10 Profile Updater v2 error")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
