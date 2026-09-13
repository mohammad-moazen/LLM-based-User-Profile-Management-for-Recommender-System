"""Continue Phase 10B2 v2 with a conservative, information-preserving fallback.

Existing successful v2 states are reused because the new rule is conditional:
the primary updater path is unchanged, and the fallback is invoked only when the
primary path cannot yield a usable state. No confirmatory recommendation outcome
is read by this runner.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase10_profile_canonical_v2 import (
    POLICY_NAME,
    duplicate_count,
    parse_profile_update_v2,
)
from pure_recommender.phase10_profile_fallback_v3 import (
    FALLBACK_POLICY,
    conservative_fallback_profile,
    is_context_overflow_error,
)
from pure_recommender.pure import (
    UserProfile,
    apply_retention_guard,
    build_profile_updater_messages,
    profile_from_mapping,
    profile_updater_response_format,
)

EXPERIMENT = "phase10_confirmatory_profile_updater_v2_continue"
MAX_ATTEMPTS_PER_TASK = 3


def _load_base_runner() -> Any:
    path = REPO_ROOT / "scripts" / "run_phase10_confirmatory_profile_updater_v2_safe.py"
    spec = importlib.util.spec_from_file_location("phase10_v2_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Phase 10B2 v2 base runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _publish(payload: dict[str, object], message: str) -> None:
    ok, detail = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=message,
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {detail}")


def _fallback_row(
    *,
    phase4: Any,
    task_id: str,
    user_id: str,
    position: int,
    raw_prefix_count: int,
    concatenated: UserProfile,
    attempts_used: int,
    reason: str,
) -> tuple[dict[str, object], UserProfile]:
    updated, restored_entries, allowed_removals = conservative_fallback_profile(concatenated)
    row: dict[str, object] = {
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
            "model_selected_entries": phase4._profile_counts(concatenated)["total"],
            "safe_profile_entries": phase4._profile_counts(updated)["total"],
            "guard_restored_entries": phase4._mapping_entry_count(restored_entries),
            "guard_allowed_removals": phase4._mapping_entry_count(allowed_removals),
        },
        "guard_restored_entries": restored_entries,
        "guard_allowed_removals": allowed_removals,
        "duplicate_ids_removed_by_field": {"likes": 0, "dislikes": 0, "key_features": 0},
        "duplicate_id_occurrences_removed": 0,
        "finish_reason": None,
        "latency_seconds": 0.0,
        "usage": {},
        "attempt_number": attempts_used,
        "fallback_used": True,
        "fallback_policy": FALLBACK_POLICY,
        "fallback_reason": reason,
    }
    return row, updated


def main() -> int:
    try:
        base = _load_base_runner()
        phase4 = base._load_phase4_helpers()
        freeze, grouped = base._preflight(phase4)

        llm_cfg = load_local_llm_config(REPO_ROOT / "config/local_llm.toml")
        client = OpenAICompatibleLLMClient(
            base_url=llm_cfg.base_url,
            timeout_seconds=llm_cfg.timeout_seconds,
        )
        if llm_cfg.model not in client.list_models():
            raise RuntimeError(f"Configured model {llm_cfg.model!r} is not exposed by local server")

        base.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        latest, attempts, rows_at_start = base._load_v2_audit(base.STATES_PATH)
        successes_at_start = sum(row.get("status") == "ok" for row in latest.values())

        print("=" * 104)
        print("PHASE 10B2 v2 — CONTINUE WITH CONSERVATIVE FALLBACK")
        print("=" * 104)
        print(f"Existing successful v2 states : {successes_at_start}")
        print(f"Existing audit rows            : {rows_at_start}")
        print(f"Primary policy                 : {POLICY_NAME}")
        print(f"Fallback policy                : {FALLBACK_POLICY}")
        print("Context length                  : 8192 (unchanged)")
        print("Max Concurrent Predictions      : 1")
        print("Confirmatory outcomes inspected : NO")
        print()

        new_llm_calls = 0
        new_successes = 0
        fallback_count_this_run = 0
        unresolved: list[dict[str, object]] = []

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

                messages, concatenated, id_map = build_profile_updater_messages(profile, extraction)
                used_attempts = attempts.get(task_id, 0)
                task_ok = False

                # If the previous invocation already proved the request cannot fit
                # the frozen context, do not send the same impossible request again.
                previous_error = str(existing.get("error", "")) if isinstance(existing, dict) else ""
                if previous_error and is_context_overflow_error(previous_error):
                    state_row, profile = _fallback_row(
                        phase4=phase4,
                        task_id=task_id,
                        user_id=user_id,
                        position=position,
                        raw_prefix_count=raw_prefix_count,
                        concatenated=concatenated,
                        attempts_used=used_attempts,
                        reason="frozen_context_overflow_previously_observed",
                    )
                    _append_jsonl(base.STATES_PATH, state_row)
                    latest[task_id] = state_row
                    new_successes += 1
                    fallback_count_this_run += 1
                    print(f"  {task_id}: FALLBACK (known context overflow)")
                    continue

                # Fresh primary attempts. A context overflow is deterministic for
                # this prompt/runtime, so it immediately switches to fallback.
                while used_attempts < MAX_ATTEMPTS_PER_TASK:
                    used_attempts += 1
                    attempts[task_id] = used_attempts
                    new_llm_calls += 1
                    raw_content = ""
                    started = time.perf_counter()
                    try:
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
                            "fallback_used": False,
                        }
                        _append_jsonl(base.STATES_PATH, state_row)
                        latest[task_id] = state_row
                        profile = updated
                        new_successes += 1
                        task_ok = True
                        suffix = f" canonicalized_duplicates={dup_total}" if dup_total else ""
                        print(f"  {task_id}: OK attempt={used_attempts}{suffix}")
                        break
                    except Exception as exc:
                        elapsed = time.perf_counter() - started
                        error_text = str(exc)
                        error_row = {
                            "status": "error",
                            "policy": POLICY_NAME,
                            "task_id": task_id,
                            "user_id": user_id,
                            "interaction_position": position,
                            "error": error_text,
                            "latency_seconds": elapsed,
                            "raw_response": raw_content,
                            "attempt_number": used_attempts,
                        }
                        _append_jsonl(base.STATES_PATH, error_row)
                        latest[task_id] = error_row
                        print(f"  {task_id}: ERROR attempt={used_attempts}: {error_text}")

                        if is_context_overflow_error(exc):
                            state_row, profile = _fallback_row(
                                phase4=phase4,
                                task_id=task_id,
                                user_id=user_id,
                                position=position,
                                raw_prefix_count=raw_prefix_count,
                                concatenated=concatenated,
                                attempts_used=used_attempts,
                                reason="frozen_context_overflow",
                            )
                            _append_jsonl(base.STATES_PATH, state_row)
                            latest[task_id] = state_row
                            new_successes += 1
                            fallback_count_this_run += 1
                            task_ok = True
                            print(f"  {task_id}: FALLBACK (context overflow)")
                            break

                if not task_ok:
                    # Three unusable primary attempts are discarded. Preserve all
                    # evidence rather than failing the whole confirmatory cohort.
                    state_row, profile = _fallback_row(
                        phase4=phase4,
                        task_id=task_id,
                        user_id=user_id,
                        position=position,
                        raw_prefix_count=raw_prefix_count,
                        concatenated=concatenated,
                        attempts_used=used_attempts,
                        reason="primary_attempts_exhausted",
                    )
                    _append_jsonl(base.STATES_PATH, state_row)
                    latest[task_id] = state_row
                    new_successes += 1
                    fallback_count_this_run += 1
                    print(f"  {task_id}: FALLBACK (primary attempts exhausted)")

        aggregate = base._aggregate_latest(latest)
        latest_fallbacks = [
            row for row in latest.values()
            if row.get("status") == "ok" and row.get("fallback_used") is True
        ]
        status = (
            "PASS"
            if aggregate["successful_updates"] == base.EXPECTED_UPDATES
            and aggregate["failed_updates"] == 0
            else "INCOMPLETE"
        )

        summary: dict[str, object] = {
            "component": "Profile Updater",
            "run_version": "confirmatory_v2_with_conservative_fallback",
            "status": status,
            "model": llm_cfg.model,
            "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
            "users": base.EXPECTED_USERS,
            "expected_updates": base.EXPECTED_UPDATES,
            **aggregate,
            "generation": {"temperature": 0.0, "max_tokens": 1024, "seed": 42},
            "runtime": {
                "context_length": 8192,
                "max_concurrent_predictions": 1,
            },
            "fallback": {
                "policy": FALLBACK_POLICY,
                "latest_states_using_fallback": len(latest_fallbacks),
                "fallbacks_this_invocation": fallback_count_this_run,
                "reasons": sorted({str(row.get("fallback_reason")) for row in latest_fallbacks}),
                "semantic_effect": "preserves all distinct evidence; may reduce profile compaction only",
            },
            "homogeneity_note": (
                "Previously successful v2 states remain valid because the primary path is unchanged; "
                "the fallback is conditional and only applies when the primary path cannot yield a usable state."
            ),
            "resume": {
                "successful_states_at_start": successes_at_start,
                "new_llm_calls_this_invocation": new_llm_calls,
                "new_successes_this_invocation": new_successes,
            },
            "phase9_freeze": freeze,
            "state_artifact": str(base.STATES_PATH),
            "confirmatory_recommendation_outcomes_inspected": False,
        }
        base.SUMMARY_PATH.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        payload = {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "confirmatory_recommendation_outcomes_inspected": False,
            "summary": summary,
            "unresolved": unresolved,
        }
        _publish(
            payload,
            "handoff: phase10 Profile Updater v2 continue " + ("pass" if status == "PASS" else "incomplete"),
        )
        return 0 if status == "PASS" else 1

    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "confirmatory_recommendation_outcomes_inspected": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        _publish(payload, "handoff: phase10 Profile Updater v2 continue error")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
