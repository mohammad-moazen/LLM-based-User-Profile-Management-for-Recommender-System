"""One strict, non-repairing Profile Updater recovery attempt."""

from __future__ import annotations

import time
from typing import Any

from pure_recommender.pure import (
    apply_retention_guard,
    build_profile_updater_messages,
    parse_profile_update,
    profile_updater_response_format,
)


def run_profile_attempt(
    *,
    phase4: Any,
    client: Any,
    llm_cfg: Any,
    task_id: str,
    user_id: str,
    position: int,
    profile: Any,
    extraction: dict[str, object],
    raw_prefix_count: int,
    attempt_number: int,
) -> tuple[dict[str, object], Any]:
    """Return a valid state row and updated profile, or raise on any invalid response."""
    messages, concatenated, id_map = build_profile_updater_messages(profile, extraction)
    response_format = profile_updater_response_format(id_map)
    started = time.perf_counter()
    response = client.chat_completion(
        model=llm_cfg.model,
        messages=messages,
        temperature=0.0,
        max_tokens=1024,
        seed=42,
        response_format=response_format,
    )
    elapsed = time.perf_counter() - started
    selected = parse_profile_update(
        response.content,
        allowed_profile=concatenated,
        id_map=id_map,
    )
    updated, restored, allowed_removals = apply_retention_guard(
        selected,
        allowed_profile=concatenated,
    )
    state_row: dict[str, object] = {
        "status": "ok",
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
            "guard_restored_entries": phase4._mapping_entry_count(restored),
            "guard_allowed_removals": phase4._mapping_entry_count(allowed_removals),
        },
        "guard_restored_entries": restored,
        "guard_allowed_removals": allowed_removals,
        "finish_reason": phase4._finish_reason(response.raw),
        "latency_seconds": elapsed,
        "usage": dict(response.usage) if response.usage else {},
        "recovery_attempt": attempt_number,
        "response_repair": "none",
    }
    return state_row, updated


__all__ = ["run_profile_attempt"]
