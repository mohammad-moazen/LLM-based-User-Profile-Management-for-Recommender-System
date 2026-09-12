"""PURE Profile Updater prompt, schema, and conservative output validation.

The PURE paper concatenates the previous user profile with the newly extracted
likes/dislikes/key-features and asks an LLM to remove redundant, overlapping,
and conflicting content while preserving crucial information.

The paper publishes the natural-language updater prompt but not its exact JSON
schema or post-processing rules. This reproduction therefore uses a conservative
subset-preserving representation: the updater may remove entries, but every
returned string must be an exact member of the corresponding concatenated input
list. This prevents the updater from injecting unsupported new preference text
while still allowing it to compact redundancy and discard clear conflicts.

Pilot v1 showed that a generic "preserve crucial information" instruction still
allowed arbitrary deletion of a unique, non-conflicting entry. Pilot v2 therefore
adds a retention-biased rule: unique evidence must be preserved unless it is a
clear duplicate/overlap or a clear conflict. The model is not allowed to delete
an entry merely because it seems less relevant or because a shorter profile is
preferred.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Sequence


PROFILE_FIELDS = ("likes", "dislikes", "key_features")

PAPER_UPDATER_INSTRUCTION = (
    "You are given a list: {list}. Update this list by removing redundant or "
    "overlapping information. Note that crucial information should be preserved."
)

SYSTEM_PROMPT = (
    "You are the Profile Updater component of the PURE recommender system. "
    "Compact the evolving user profile only by removing clear duplicates, clear "
    "overlap/redundancy, or clear conflicts while preserving all other evidence. "
    "For this reproduction, you must only select from the provided strings: do "
    "not rewrite, paraphrase, invent, or move an entry to another category. "
    "Do not remove a unique non-conflicting entry merely to make the profile shorter."
)


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


def profile_updater_response_format() -> dict[str, object]:
    """Return the project-defined strict structured-output schema."""

    properties = {
        field_name: {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": (
                "Retention-biased compact subset of the corresponding provided "
                "input strings; do not introduce new text."
            ),
        }
        for field_name in PROFILE_FIELDS
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "pure_profile_update_subset",
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
) -> tuple[list[dict[str, str]], UserProfile]:
    """Build one chronological Profile Updater request.

    Returns both the messages and the exact concatenated profile that forms the
    allow-list for deterministic output validation.
    """

    concatenated = concatenate_profile_and_extraction(previous_profile, new_extraction)
    payload = concatenated.to_dict()
    user_prompt = (
        "Paper prompt template:\n"
        f"{PAPER_UPDATER_INSTRUCTION}\n\n"
        "The strings in each category are ordered chronologically: older profile "
        "evidence appears before newly appended evidence.\n\n"
        "Apply the paper update to the following categorized profile lists:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "REPRODUCTION CONSTRAINTS — FOLLOW STRICTLY:\n"
        "1. Retain every unique entry by default.\n"
        "2. Remove an entry ONLY when it is an exact duplicate, clearly redundant/overlapping with another retained entry, or clearly conflicts with other evidence.\n"
        "3. Do NOT remove a unique non-overlapping, non-conflicting entry merely because it seems less relevant or to make the profile shorter.\n"
        "4. For clear overlap, keep the entry that preserves the more specific/informative evidence.\n"
        "5. For a clear direct conflict, prefer the newer evidence only when the conflict is unambiguous; if uncertain, preserve both rather than silently deleting information.\n"
        "6. Preserve crucial information.\n"
        "7. Every output string MUST be copied exactly from the same input category.\n"
        "8. Do not paraphrase, summarize into new wording, invent, or add outside knowledge.\n"
        "9. Do not move strings between likes, dislikes, and key_features.\n"
        "10. Do not return duplicate strings within a category.\n"
        "11. Empty arrays are allowed only when no input entry in that category should be retained under the rules above.\n"
        "Return only the structured response required by the JSON schema."
    )
    return (
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        concatenated,
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


def _validate_subset_list(
    payload: object,
    *,
    field_name: str,
    allowed_values: Sequence[str],
) -> tuple[str, ...]:
    if not isinstance(payload, list):
        raise ValueError(f"Profile Updater field {field_name!r} must be an array")

    allowed = set(allowed_values)
    seen: set[str] = set()
    result: list[str] = []
    for item in payload:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Profile Updater field {field_name!r} contains invalid text")
        value = item.strip()
        if value not in allowed:
            raise ValueError(
                f"Profile Updater field {field_name!r} introduced unsupported text: {value!r}"
            )
        if value in seen:
            raise ValueError(
                f"Profile Updater field {field_name!r} returned duplicate text: {value!r}"
            )
        seen.add(value)
        result.append(value)
    return tuple(result)


def parse_profile_update(text: str, *, allowed_profile: UserProfile) -> UserProfile:
    """Parse and mechanically enforce the subset-preserving updater contract."""

    payload = _extract_json_object(text)
    expected_keys = set(PROFILE_FIELDS)
    actual_keys = set(payload)
    if actual_keys != expected_keys:
        raise ValueError(
            "Profile Updater response has incorrect keys; "
            f"missing={sorted(expected_keys - actual_keys)}, "
            f"unexpected={sorted(actual_keys - expected_keys)}"
        )

    return UserProfile(
        likes=_validate_subset_list(
            payload["likes"], field_name="likes", allowed_values=allowed_profile.likes
        ),
        dislikes=_validate_subset_list(
            payload["dislikes"],
            field_name="dislikes",
            allowed_values=allowed_profile.dislikes,
        ),
        key_features=_validate_subset_list(
            payload["key_features"],
            field_name="key_features",
            allowed_values=allowed_profile.key_features,
        ),
    )
