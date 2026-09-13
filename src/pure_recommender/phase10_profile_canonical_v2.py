"""Phase 10B2 v2 parsing policy for robust confirmatory Profile Updater execution.

The local model occasionally produces structurally invalid updater output on long
prefixes. This module treats such failures conservatively: invalid model content
is discarded completely and the already-accepted Phase 4 v4 retention guard is
applied to the full concatenated profile. This preserves unique evidence and can
only collapse exact duplicates or shorter entries strictly dominated by richer
same-category evidence.
"""

from __future__ import annotations

import json
from typing import Mapping

from pure_recommender.pure import (
    UserProfile,
    apply_retention_guard,
    concatenate_profile_and_extraction,
    parse_profile_update,
)
from pure_recommender.pure.profile_updater import PROFILE_FIELDS

POLICY_NAME = "exact_duplicate_id_canonicalization_v2"
FALLBACK_POLICY_NAME = "guard_only_after_invalid_llm_output_v1"


def _extract_json_object(text: str) -> dict[str, object]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Profile Updater response does not contain a JSON object")

    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Profile Updater response contains invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Profile Updater response must be a JSON object")
    return payload


def canonicalize_exact_duplicate_ids(
    text: str,
    *,
    id_map: Mapping[str, Mapping[str, str]],
) -> tuple[str, dict[str, int]]:
    payload = _extract_json_object(text)
    expected_keys = set(PROFILE_FIELDS)
    actual_keys = set(payload)
    if actual_keys != expected_keys:
        raise ValueError(
            "Profile Updater response has incorrect keys; "
            f"missing={sorted(expected_keys - actual_keys)}, "
            f"unexpected={sorted(actual_keys - expected_keys)}"
        )

    normalized: dict[str, list[str]] = {}
    removed: dict[str, int] = {}
    for field_name in PROFILE_FIELDS:
        values = payload[field_name]
        if not isinstance(values, list):
            raise ValueError(f"Profile Updater field {field_name!r} must be an array")

        valid_ids = id_map[field_name]
        seen: set[str] = set()
        kept: list[str] = []
        duplicate_count = 0
        for item in values:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Profile Updater field {field_name!r} contains invalid ID text")
            entry_id = item.strip()
            if entry_id not in valid_ids:
                raise ValueError(
                    f"Profile Updater field {field_name!r} returned unknown/cross-category ID: {entry_id!r}"
                )
            if entry_id in seen:
                duplicate_count += 1
                continue
            seen.add(entry_id)
            kept.append(entry_id)

        normalized[field_name] = kept
        removed[field_name] = duplicate_count

    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":")), removed


def deterministic_guard_only_update(
    previous_profile: UserProfile,
    new_extraction: Mapping[str, object],
) -> tuple[UserProfile, UserProfile, dict[str, list[str]], dict[str, list[str]]]:
    concatenated = concatenate_profile_and_extraction(previous_profile, new_extraction)
    updated, restored, removals = apply_retention_guard(
        concatenated,
        allowed_profile=concatenated,
    )
    return updated, concatenated, restored, removals


def parse_profile_update_v2(
    text: str,
    *,
    allowed_profile: UserProfile,
    id_map: Mapping[str, Mapping[str, str]],
) -> tuple[UserProfile, dict[str, int]]:
    """Parse valid output; otherwise discard it and preserve the safe profile.

    The special ``_structural_fallback`` marker is written into the audit mapping
    returned to the runner. It is not a profile field and is ignored by the
    duplicate counter.
    """

    try:
        normalized_text, removed = canonicalize_exact_duplicate_ids(text, id_map=id_map)
        parsed = parse_profile_update(
            normalized_text,
            allowed_profile=allowed_profile,
            id_map={field: dict(values) for field, values in id_map.items()},
        )
        removed["_structural_fallback"] = 0
        return parsed, removed
    except ValueError:
        safe, _, _ = apply_retention_guard(
            allowed_profile,
            allowed_profile=allowed_profile,
        )
        marker = {field: 0 for field in PROFILE_FIELDS}
        marker["_structural_fallback"] = 1
        return safe, marker


def duplicate_count(removed: Mapping[str, int]) -> int:
    return sum(int(removed.get(field, 0)) for field in PROFILE_FIELDS)


__all__ = [
    "FALLBACK_POLICY_NAME",
    "POLICY_NAME",
    "canonicalize_exact_duplicate_ids",
    "deterministic_guard_only_update",
    "duplicate_count",
    "parse_profile_update_v2",
]
