"""PURE Profile Updater prompt, schema, and conservative output validation.

The PURE paper concatenates the previous user profile with the newly extracted
likes/dislikes/key-features and asks an LLM to remove redundant, overlapping,
and conflicting content while preserving crucial information.

The paper publishes the natural-language updater prompt but not its exact JSON
schema or post-processing rules. This reproduction therefore keeps the paper's
semantic role while adding deterministic safeguards that are explicit project
choices.

Pilot v1 showed arbitrary deletion of unique evidence. Pilot v2 strengthened the
prompt, but the model still deleted unrelated unique entries and also rewrote one
input string, which violated the exact-subset contract. Pilot v3 therefore uses
stable entry IDs instead of asking the model to copy long strings, and applies a
deterministic retention guard after the model decision. The guard only permits a
model-requested deletion when the omitted entry has clear lexical overlap with a
retained same-category entry. Otherwise the omitted unique entry is restored.
This prevents accidental information loss while still allowing exact duplicates
and obvious overlapping evidence to be compacted.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Mapping, Sequence


PROFILE_FIELDS = ("likes", "dislikes", "key_features")
_FIELD_PREFIX = {"likes": "L", "dislikes": "D", "key_features": "K"}

PAPER_UPDATER_INSTRUCTION = (
    "You are given a list: {list}. Update this list by removing redundant or "
    "overlapping information. Note that crucial information should be preserved."
)

SYSTEM_PROMPT = (
    "You are the Profile Updater component of the PURE recommender system. "
    "Compact the evolving user profile only by removing clear duplicates, clear "
    "overlap/redundancy, or clear conflicts while preserving all other evidence. "
    "Each entry has a stable ID. Return IDs only; never rewrite profile text. "
    "Do not remove a unique non-conflicting entry merely to make the profile shorter."
)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "you",
    "your",
}


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Compact structured user profile used by downstream PURE components."""

    likes: tuple[str, ...] = ()
    dislikes: tuple[str, ...] = ()
    key_features: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "likes": list(self.likes),
            "dislikes": list(self.dislikes),
            "key_features": list(self.key_features),
        }


ProfileIdMap = dict[str, dict[str, str]]


def _clean_input_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Profile field {field_name!r} must be a list/tuple of strings")

    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Profile field {field_name!r} contains an invalid string")
        cleaned.append(item.strip())
    return cleaned


def profile_from_mapping(value: Mapping[str, object]) -> UserProfile:
    """Validate a profile-like mapping and return an immutable UserProfile."""

    actual_keys = set(value)
    expected_keys = set(PROFILE_FIELDS)
    if actual_keys != expected_keys:
        raise ValueError(
            "Profile mapping has incorrect keys; "
            f"missing={sorted(expected_keys - actual_keys)}, "
            f"unexpected={sorted(actual_keys - expected_keys)}"
        )

    return UserProfile(
        likes=tuple(_clean_input_list(value["likes"], "likes")),
        dislikes=tuple(_clean_input_list(value["dislikes"], "dislikes")),
        key_features=tuple(_clean_input_list(value["key_features"], "key_features")),
    )


def concatenate_profile_and_extraction(
    previous_profile: UserProfile,
    new_extraction: Mapping[str, object],
) -> UserProfile:
    """Implement Algorithm 1's concatenation before Profile Updater U(·)."""

    incoming = profile_from_mapping(new_extraction)
    return UserProfile(
        likes=previous_profile.likes + incoming.likes,
        dislikes=previous_profile.dislikes + incoming.dislikes,
        key_features=previous_profile.key_features + incoming.key_features,
    )


def build_profile_id_map(profile: UserProfile) -> ProfileIdMap:
    """Assign deterministic same-category IDs to every concatenated input entry."""

    result: ProfileIdMap = {}
    for field_name in PROFILE_FIELDS:
        prefix = _FIELD_PREFIX[field_name]
        values = getattr(profile, field_name)
        result[field_name] = {
            f"{prefix}{index:03d}": value
            for index, value in enumerate(values, start=1)
        }
    return result


def _id_array_schema(valid_ids: Sequence[str]) -> dict[str, object]:
    item_schema: dict[str, object] = {"type": "string"}
    if valid_ids:
        item_schema["enum"] = list(valid_ids)
    schema: dict[str, object] = {
        "type": "array",
        "items": item_schema,
        "description": "IDs of entries to retain from this category.",
    }
    if not valid_ids:
        schema["maxItems"] = 0
    return schema


def profile_updater_response_format(id_map: ProfileIdMap) -> dict[str, object]:
    """Return a strict ID-only structured-output schema for one updater call."""

    properties = {
        field_name: _id_array_schema(tuple(id_map[field_name]))
        for field_name in PROFILE_FIELDS
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "pure_profile_update_ids",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": list(PROFILE_FIELDS),
                "additionalProperties": False,
            },
        },
    }


def build_profile_updater_messages(
    previous_profile: UserProfile,
    new_extraction: Mapping[str, object],
) -> tuple[list[dict[str, str]], UserProfile, ProfileIdMap]:
    """Build one chronological ID-based Profile Updater request.

    Returns the messages, exact concatenated profile, and the deterministic ID
    mapping used both by the JSON schema and by the parser.
    """

    concatenated = concatenate_profile_and_extraction(previous_profile, new_extraction)
    id_map = build_profile_id_map(concatenated)
    labeled_payload = {
        field_name: [
            {"id": entry_id, "text": text}
            for entry_id, text in id_map[field_name].items()
        ]
        for field_name in PROFILE_FIELDS
    }

    user_prompt = (
        "Paper prompt template:\n"
        f"{PAPER_UPDATER_INSTRUCTION}\n\n"
        "The entries in each category are ordered chronologically: older profile "
        "evidence appears before newly appended evidence.\n\n"
        "Apply the paper update to these categorized entries:\n"
        f"{json.dumps(labeled_payload, ensure_ascii=False, indent=2)}\n\n"
        "REPRODUCTION CONSTRAINTS — FOLLOW STRICTLY:\n"
        "1. Return only the IDs of entries that should remain in each category.\n"
        "2. Retain every unique entry by default.\n"
        "3. Remove an entry ONLY when it is an exact duplicate, clearly redundant/overlapping with another retained entry, or clearly conflicts with other evidence.\n"
        "4. Do NOT remove a unique non-overlapping, non-conflicting entry merely because it seems less relevant or to make the profile shorter.\n"
        "5. For clear overlap, keep the entry that preserves the more specific/informative evidence.\n"
        "6. For a clear direct conflict, prefer newer evidence only when the conflict is unambiguous; if uncertain, preserve both.\n"
        "7. Preserve crucial information.\n"
        "8. Never copy or rewrite the text itself; output IDs only.\n"
        "9. Never use an ID from another category.\n"
        "10. Do not return duplicate IDs.\n"
        "Return only the structured response required by the JSON schema."
    )
    return (
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        concatenated,
        id_map,
    )


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


def _validate_id_list(
    payload: object,
    *,
    field_name: str,
    id_map: Mapping[str, str],
) -> tuple[str, ...]:
    if not isinstance(payload, list):
        raise ValueError(f"Profile Updater field {field_name!r} must be an array")

    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    result: list[str] = []
    for item in payload:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Profile Updater field {field_name!r} contains invalid ID text")
        entry_id = item.strip()
        if entry_id not in id_map:
            raise ValueError(
                f"Profile Updater field {field_name!r} returned unknown/cross-category ID: {entry_id!r}"
            )
        if entry_id in seen_ids:
            raise ValueError(
                f"Profile Updater field {field_name!r} returned duplicate ID: {entry_id!r}"
            )
        seen_ids.add(entry_id)
        value = id_map[entry_id]
        if value not in seen_text:
            result.append(value)
            seen_text.add(value)
    return tuple(result)


def parse_profile_update(
    text: str,
    *,
    allowed_profile: UserProfile,
    id_map: ProfileIdMap,
) -> UserProfile:
    """Parse model-selected IDs and map them back to exact input strings."""

    payload = _extract_json_object(text)
    expected_keys = set(PROFILE_FIELDS)
    actual_keys = set(payload)
    if actual_keys != expected_keys:
        raise ValueError(
            "Profile Updater response has incorrect keys; "
            f"missing={sorted(expected_keys - actual_keys)}, "
            f"unexpected={sorted(actual_keys - expected_keys)}"
        )

    expected_id_map = build_profile_id_map(allowed_profile)
    if id_map != expected_id_map:
        raise ValueError("Profile Updater ID map does not match the allowed concatenated profile")

    return UserProfile(
        likes=_validate_id_list(payload["likes"], field_name="likes", id_map=id_map["likes"]),
        dislikes=_validate_id_list(
            payload["dislikes"], field_name="dislikes", id_map=id_map["dislikes"]
        ),
        key_features=_validate_id_list(
            payload["key_features"],
            field_name="key_features",
            id_map=id_map["key_features"],
        ),
    )


def _normalize_for_overlap(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    return " ".join(tokens)


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if token not in _STOPWORDS and len(token) > 1
    }


def is_clear_lexical_overlap(left: str, right: str) -> bool:
    """Conservatively recognize only obvious same-category lexical overlap.

    This is intentionally not a semantic similarity model. It is a mechanical
    safety gate for deletions requested by the LLM.
    """

    left_norm = _normalize_for_overlap(left)
    right_norm = _normalize_for_overlap(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    if len(left_norm) >= 12 and len(right_norm) >= 12:
        if left_norm in right_norm or right_norm in left_norm:
            return True

    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    intersection = left_tokens & right_tokens
    smaller = min(len(left_tokens), len(right_tokens))
    union = left_tokens | right_tokens
    if len(intersection) < 3 or smaller == 0 or not union:
        return False

    containment = len(intersection) / smaller
    jaccard = len(intersection) / len(union)
    return containment >= 0.80 and jaccard >= 0.50


def apply_retention_guard(
    model_selected: UserProfile,
    *,
    allowed_profile: UserProfile,
) -> tuple[UserProfile, dict[str, list[str]], dict[str, list[str]]]:
    """Restore unsupported deletions and keep only mechanically defensible removals.

    The model may request deletion by omitting an ID. For each unique omitted
    string, deletion is allowed only when a retained same-category string has
    clear lexical overlap. Otherwise the string is restored. Exact duplicate
    input strings collapse to one retained occurrence.

    Returns ``(safe_profile, restored_entries, allowed_removals)``.
    """

    safe_fields: dict[str, tuple[str, ...]] = {}
    restored: dict[str, list[str]] = {field: [] for field in PROFILE_FIELDS}
    allowed_removals: dict[str, list[str]] = {field: [] for field in PROFILE_FIELDS}

    for field_name in PROFILE_FIELDS:
        original_values = list(getattr(allowed_profile, field_name))
        selected_values = list(dict.fromkeys(getattr(model_selected, field_name)))
        selected_set = set(selected_values)

        unique_original = list(dict.fromkeys(original_values))
        safe_values: list[str] = []
        for value in unique_original:
            if value in selected_set:
                safe_values.append(value)
                continue

            witnesses = [
                kept
                for kept in selected_values
                if kept != value and is_clear_lexical_overlap(value, kept)
            ]
            if witnesses:
                allowed_removals[field_name].append(value)
            else:
                safe_values.append(value)
                restored[field_name].append(value)

        safe_fields[field_name] = tuple(safe_values)

    return (
        UserProfile(
            likes=safe_fields["likes"],
            dislikes=safe_fields["dislikes"],
            key_features=safe_fields["key_features"],
        ),
        restored,
        allowed_removals,
    )
