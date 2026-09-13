"""Homogeneous Phase 10B2 v2 parsing and fallback policy for Profile Updater outputs.

Only one narrow structural defect is canonicalized: repeated occurrences of the
same valid ID inside the same category. Profile Updater output is semantically a
selection of retained IDs, so repeating an already-selected ID does not add any
new selection information. Removing only that repeated occurrence preserves the
selected set exactly.

Everything else remains strict. Unknown IDs, cross-category IDs, wrong keys,
malformed JSON, invalid types, and empty IDs are rejected.

For long prefixes that remain structurally invalid after the frozen retry budget,
v2 also provides a conservative deterministic fallback. The invalid model output
is discarded completely. The fallback concatenates the previous safe profile and
the new extraction and then runs the already-accepted Phase 4 v4 retention guard
with every entry selected. Therefore it can only collapse exact duplicates or
remove a shorter same-category entry strictly dominated by richer evidence. It
never invents or drops unique evidence because of a malformed LLM response.
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
FALLBACK_POLICY_NAME = "guard_only_after_invalid_llm_budget_v1"


def _extract_json_object(text: str) -> dict[str, object]:
    """Extract one JSON object using the same tolerant fence handling as Phase 4."""

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
    """Remove repeated occurrences of an already-selected valid ID only.

    The first occurrence is retained and order is preserved. This is equivalent
    to canonicalizing a set-valued selection representation; it does not infer,
    add, remove, or rewrite any distinct model selection.
    """

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


def parse_profile_update_v2(
    text: str,
    *,
    allowed_profile: UserProfile,
    id_map: Mapping[str, Mapping[str, str]],
) -> tuple[UserProfile, dict[str, int]]:
    """Canonicalize exact duplicate IDs, then reuse the strict accepted parser."""

    normalized_text, removed = canonicalize_exact_duplicate_ids(text, id_map=id_map)
    parsed = parse_profile_update(
        normalized_text,
        allowed_profile=allowed_profile,
        id_map={field: dict(values) for field, values in id_map.items()},
    )
    return parsed, removed


def deterministic_guard_only_update(
    previous_profile: UserProfile,
    new_extraction: Mapping[str, object],
) -> tuple[UserProfile, UserProfile, dict[str, list[str]], dict[str, list[str]]]:
    """Conservatively advance one profile without using an invalid LLM output.

    Every concatenated entry is treated as selected. The accepted v4 guard then
    performs only its deterministic safe operations: exact-duplicate collapse
    and removal of shorter entries strictly dominated by richer same-category
    evidence. Unique evidence is preserved.
    """

    concatenated = concatenate_profile_and_extraction(previous_profile, new_extraction)
    updated, restored, allowed_removals = apply_retention_guard(
        concatenated,
        allowed_profile=concatenated,
    )
    return updated, concatenated, restored, allowed_removals


def duplicate_count(removed: Mapping[str, int]) -> int:
    """Return the total number of repeated ID occurrences removed."""

    return sum(int(removed.get(field, 0)) for field in PROFILE_FIELDS)


__all__ = [
    "FALLBACK_POLICY_NAME",
    "POLICY_NAME",
    "canonicalize_exact_duplicate_ids",
    "deterministic_guard_only_update",
    "duplicate_count",
    "parse_profile_update_v2",
]
