"""Chronological Phase 10B2 recovery with explicit unique-ID schema enforcement."""

from __future__ import annotations

from typing import Any

from pure_recommender.phase10_profile_schema_recovery import (
    MAX_SCHEMA_ATTEMPTS_PER_TASK,
    RECOVERY_POLICY,
    load_schema_attempts,
    run_hardened_attempt,
)
from pure_recommender.pure import UserProfile, profile_from_mapping


def resume_profile_updates(ctx: dict[str, Any]) -> tuple[int, int, list[dict[str, object]]]:
    phase4 = ctx["phase4"]
    latest = ctx["latest"]
    states_path = ctx["states_path"]
    attempts = load_schema_attempts(states_path)
    new_successes = 0
    new_calls = 0
    unresolved: list[dict[str, object]] = []

    for user_index, (user_id, user_rows) in enumerate(ctx["grouped"], start=1):
        profile = UserProfile()
        raw_unique = {field: [] for field in phase4.PROFILE_FIELDS}
        print(f"USER {user_index}/{len(ctx['grouped'])} {user_id} ({len(user_rows)} updates)")

        for row in user_rows:
            task_id = str(row["task_id"])
            position = int(row["interaction_position"])
            extraction_obj = row["extraction"]
            assert isinstance(extraction_obj, dict)

            phase4._add_to_raw_unique_profile(raw_unique, extraction_obj)
            raw_prefix_count = phase4._raw_unique_count(raw_unique)
            existing = latest.get(task_id)

            if existing is not None and existing.get("status") == "ok":
                if str(existing.get("user_id")) != user_id or int(existing.get("interaction_position", -1)) != position:
                    raise RuntimeError(f"Stored state identity mismatch for {task_id}")
                mapping = existing.get("profile")
                if not isinstance(mapping, dict):
                    raise RuntimeError(f"Stored profile invalid for {task_id}")
                profile = profile_from_mapping(mapping)
                continue

            used = attempts.get(task_id, 0)
            task_ok = False
            while used < MAX_SCHEMA_ATTEMPTS_PER_TASK:
                used += 1
                attempts[task_id] = used
                new_calls += 1
                try:
                    state_row, updated = run_hardened_attempt(
                        phase4=phase4,
                        client=ctx["client"],
                        llm_cfg=ctx["llm_cfg"],
                        task_id=task_id,
                        user_id=user_id,
                        position=position,
                        profile=profile,
                        extraction=extraction_obj,
                        raw_prefix_count=raw_prefix_count,
                        attempt_number=used,
                    )
                    phase4._append_jsonl(states_path, state_row)
                    latest[task_id] = state_row
                    profile = updated
                    new_successes += 1
                    task_ok = True
                    print(f"  {task_id}: OK on schema-hardened attempt {used}")
                    break
                except Exception as exc:
                    error_row = {
                        "status": "error",
                        "task_id": task_id,
                        "user_id": user_id,
                        "interaction_position": position,
                        "error": str(exc),
                        "recovery_policy": RECOVERY_POLICY,
                        "schema_recovery_attempt": used,
                        "schema_unique_items_enforced": True,
                        "response_repair": "none",
                    }
                    phase4._append_jsonl(states_path, error_row)
                    latest[task_id] = error_row
                    print(f"  {task_id}: schema-hardened attempt {used} ERROR: {exc}")

            if not task_ok:
                unresolved.append(
                    {
                        "task_id": task_id,
                        "user_id": user_id,
                        "interaction_position": position,
                        "error": latest[task_id].get("error"),
                    }
                )
                break
        if unresolved:
            break

    return new_successes, new_calls, unresolved


__all__ = ["resume_profile_updates"]
