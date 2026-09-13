"""Helpers for auditable Phase 10B2 Profile Updater recovery."""

from __future__ import annotations

import json
from pathlib import Path
import statistics
from typing import Mapping


def load_state_audit(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, int], int]:
    """Return latest task rows, recorded recovery-attempt counts, and total audit rows."""
    latest: dict[str, dict[str, object]] = {}
    recovery_attempts: dict[str, int] = {}
    rows_total = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows_total += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            if not isinstance(row, dict) or not isinstance(row.get("task_id"), str):
                raise ValueError(f"Invalid state row at {path}:{line_number}")
            task_id = str(row["task_id"])
            latest[task_id] = row
            marker = row.get("recovery_attempt")
            if isinstance(marker, int) and marker > 0:
                recovery_attempts[task_id] = max(recovery_attempts.get(task_id, 0), marker)
    return latest, recovery_attempts, rows_total


def mapping_entry_count(value: object) -> int:
    if not isinstance(value, Mapping):
        return 0
    return sum(len(entries) for entries in value.values() if isinstance(entries, list))


def aggregate_latest_states(latest: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    """Aggregate only each task's latest state so prior failed attempts stay audit-only."""
    ok_rows = [row for row in latest.values() if row.get("status") == "ok"]
    bad_rows = [row for row in latest.values() if row.get("status") != "ok"]
    prompt_tokens = completion_tokens = total_tokens = 0
    max_prompt_tokens = 0
    max_prompt_task_id: str | None = None
    restored = removed = 0
    latencies: list[float] = []

    for row in ok_rows:
        latency = row.get("latency_seconds")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))
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
        restored += mapping_entry_count(row.get("guard_restored_entries"))
        removed += mapping_entry_count(row.get("guard_allowed_removals"))

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
        "latency": {
            "total_seconds": sum(latencies),
            "mean_seconds": statistics.mean(latencies) if latencies else 0.0,
            "median_seconds": statistics.median(latencies) if latencies else 0.0,
        },
    }


__all__ = ["aggregate_latest_states", "load_state_audit", "mapping_entry_count"]
