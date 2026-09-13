"""Schema-hardened, non-repairing recovery for Phase 10B2.

The accepted Profile Updater prompt already says that duplicate IDs are invalid,
and the strict parser has always rejected them. During the confirmatory run one
long profile task repeatedly returned the same duplicate ID even across fresh
requests. This module strengthens only the JSON-schema enforcement of that
already-existing invariant by adding ``uniqueItems: true`` to each ID array.

No generated response is edited, deduplicated, or repaired. Previously accepted
states remain valid because they already passed the strict duplicate-rejecting
parser. The hardening is introduced before any confirmatory recommendation
outcome has been inspected.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Mapping

from pure_recommender.pure import (
    PROFILE_FIELDS,
    apply_retention_guard,
    build_profile_updater_messages,
    parse_profile_update,
    profile_updater_response_format,
)

RECOVERY_POLICY = "schema_unique_items_v2"
MAX_SCHEMA_ATTEMPTS_PER_TASK = 3


def hardened_profile_updater_response_format(id_map: Mapping[str, Mapping[str, str]]) -> dict[str, object]:
    """Return the accepted updater schema with duplicate IDs forbidden explicitly."""

    response_format = profile_updater_response_format(dict(id_map))
    schema = response_format["json_schema"]["schema"]
    properties = schema["properties"]
    for field_name in PROFILE_FIELDS:
        properties[field_name]["uniqueItems"] = True
    return response_format


def load_schema_attempts(path: Path) -> dict[str, int]:
    """Return the largest v2 schema-recovery attempt recorded for each task."""

    attempts: dict[str, int] = {}
    if not path.exists():
        return attempts
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Invalid state row at {path}:{line_number}")
            if row.get("recovery_policy") != RECOVERY_POLICY:
                continue
            task_id = row.get("task_id")
            marker = row.get("schema_recovery_attempt")
            if isinstance(task_id, str) and isinstance(marker, int) and marker > 0:
                attempts[task_id] = max(attempts.get(task_id, 0), marker)
    return attempts


def run_hardened_attempt(
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
    """Run one fresh request under the schema-hardened but semantically identical contract."""

    messages, concatenated, id_map = build_profile_updater_messages(profile, extraction)
    response_format = hardened_profile_updater_response_format(id_map)
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
        "recovery_policy": RECOVERY_POLICY,
        "schema_recovery_attempt": attempt_number,
        "schema_unique_items_enforced": True,
        "response_repair": "none",
    }
    return state_row, updated


__all__ = [
    "MAX_SCHEMA_ATTEMPTS_PER_TASK",
    "RECOVERY_POLICY",
    "hardened_profile_updater_response_format",
    "load_schema_attempts",
    "run_hardened_attempt",
]
