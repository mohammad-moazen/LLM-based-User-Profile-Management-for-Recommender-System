"""Helpers for Phase 10A hardware-saturation validation.

The confirmatory cohort is already frozen. This module deliberately separates
scientific-input verification from a synthetic throughput probe so hardware
settings can be evaluated before any confirmatory model output is observed.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Mapping, Sequence

from .confirmatory_cohort import canonical_sha256


def _read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_json_records(path: Path) -> list[dict[str, object]]:
    """Load a JSON array of objects with strict shape validation."""

    value = _read_json(path)
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"Expected a JSON array of objects in {path}")
    return [dict(row) for row in value]


def load_jsonl_gz_records(path: Path) -> list[dict[str, object]]:
    """Load a gzip-compressed JSONL artifact."""

    rows: list[dict[str, object]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object in {path} at line {line_number}")
            rows.append(row)
    return rows


def verify_phase9_freeze(
    *,
    cohort_users_path: Path,
    sessions_path: Path,
    cohort_summary_path: Path,
    expected_cohort_sha256: str,
    expected_sessions_sha256: str,
    expected_users: int,
    expected_sessions: int,
) -> dict[str, object]:
    """Verify Phase 9 manifests against the pre-declared hashes.

    Phase 10 must fail before any LLM request if the local cohort/session files do
    not match the exact manifests frozen by Phase 9.
    """

    for path in (cohort_users_path, sessions_path, cohort_summary_path):
        if not path.exists():
            raise FileNotFoundError(f"Required Phase 9 artifact not found: {path}")

    cohort_users = load_json_records(cohort_users_path)
    sessions = load_jsonl_gz_records(sessions_path)
    summary = _read_json(cohort_summary_path)
    if not isinstance(summary, dict):
        raise ValueError(f"Expected JSON object in {cohort_summary_path}")

    actual_cohort_hash = canonical_sha256(cohort_users)
    actual_sessions_hash = canonical_sha256(sessions)

    if len(cohort_users) != expected_users:
        raise ValueError(f"Expected {expected_users} Phase 9 users; found {len(cohort_users)}")
    if len(sessions) != expected_sessions:
        raise ValueError(f"Expected {expected_sessions} Phase 9 sessions; found {len(sessions)}")
    if actual_cohort_hash != expected_cohort_sha256:
        raise ValueError(
            "Phase 9 cohort manifest hash mismatch; refusing Phase 10: "
            f"expected={expected_cohort_sha256}, actual={actual_cohort_hash}"
        )
    if actual_sessions_hash != expected_sessions_sha256:
        raise ValueError(
            "Phase 9 session manifest hash mismatch; refusing Phase 10: "
            f"expected={expected_sessions_sha256}, actual={actual_sessions_hash}"
        )

    summary_cohort_hash = str(summary.get("cohort_manifest_sha256", ""))
    summary_sessions_hash = str(summary.get("sessions_sha256", ""))
    if summary_cohort_hash and summary_cohort_hash != expected_cohort_sha256:
        raise ValueError("Phase 9 summary cohort hash disagrees with frozen config")
    if summary_sessions_hash and summary_sessions_hash != expected_sessions_sha256:
        raise ValueError("Phase 9 summary session hash disagrees with frozen config")

    return {
        "users": len(cohort_users),
        "sessions": len(sessions),
        "cohort_sha256": actual_cohort_hash,
        "sessions_sha256": actual_sessions_hash,
    }


def canonical_json_content(content: str) -> str:
    """Canonicalize one structured response for repeatability comparison."""

    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Probe response must be a JSON object")
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def evaluate_concurrency_candidate(
    *,
    sequential_outputs: Sequence[str],
    concurrent_outputs: Sequence[str],
    sequential_wall_seconds: float,
    concurrent_wall_seconds: float,
    min_throughput_speedup: float,
    peak_vram_used_mib: float | None,
    vram_total_mib: float | None,
    max_vram_fraction: float,
) -> dict[str, object]:
    """Apply conservative acceptance gates to the two-worker candidate.

    The candidate is accepted only when every structured output matches the
    sequential reference, throughput improves materially, and measured VRAM (if
    available) remains below the configured ceiling.
    """

    if len(sequential_outputs) != len(concurrent_outputs) or not sequential_outputs:
        raise ValueError("Sequential/concurrent probe outputs must be non-empty and aligned")
    if sequential_wall_seconds <= 0.0 or concurrent_wall_seconds <= 0.0:
        raise ValueError("Benchmark wall times must be positive")

    canonical_sequential = [canonical_json_content(value) for value in sequential_outputs]
    canonical_concurrent = [canonical_json_content(value) for value in concurrent_outputs]
    exact_matches = sum(a == b for a, b in zip(canonical_sequential, canonical_concurrent))
    exact_match_rate = exact_matches / len(canonical_sequential)
    speedup = sequential_wall_seconds / concurrent_wall_seconds

    vram_fraction: float | None = None
    vram_ok = True
    if peak_vram_used_mib is not None and vram_total_mib not in (None, 0.0):
        vram_fraction = peak_vram_used_mib / float(vram_total_mib)
        vram_ok = vram_fraction <= max_vram_fraction

    accepted = (
        exact_match_rate == 1.0
        and speedup >= min_throughput_speedup
        and vram_ok
    )

    reasons: list[str] = []
    if exact_match_rate != 1.0:
        reasons.append("concurrent_outputs_not_exactly_repeatable")
    if speedup < min_throughput_speedup:
        reasons.append("throughput_speedup_below_threshold")
    if not vram_ok:
        reasons.append("vram_headroom_below_threshold")

    return {
        "accepted": accepted,
        "recommended_max_concurrent_predictions": 2 if accepted else 1,
        "exact_matches": exact_matches,
        "probe_count": len(canonical_sequential),
        "exact_match_rate": exact_match_rate,
        "sequential_wall_seconds": sequential_wall_seconds,
        "concurrent_wall_seconds": concurrent_wall_seconds,
        "throughput_speedup": speedup,
        "peak_vram_used_mib": peak_vram_used_mib,
        "vram_total_mib": vram_total_mib,
        "peak_vram_fraction": vram_fraction,
        "vram_check_available": vram_fraction is not None,
        "rejection_reasons": reasons,
    }


__all__ = [
    "canonical_json_content",
    "evaluate_concurrency_candidate",
    "load_json_records",
    "load_jsonl_gz_records",
    "verify_phase9_freeze",
]
