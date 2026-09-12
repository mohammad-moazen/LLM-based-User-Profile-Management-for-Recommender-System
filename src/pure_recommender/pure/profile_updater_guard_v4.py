"""Information-preserving retention guard for Profile Updater pilot v4.

Pilot v3 proved that ID-only output removes model rewriting failures and that a
post-generation retention guard can protect unrelated unique evidence. One
remaining issue was directional: a shorter overlapping sentence could be kept
while a longer, more informative sentence was deleted. The v4 guard therefore
permits overlap deletion only when a retained entry is at least as informative
as the omitted entry. After restoring unsupported omissions, it also
mechanically removes any shorter entry that is strictly dominated by a longer
same-category overlap.

This module is an explicit reproduction safeguard; the PURE paper does not
publish this deterministic post-processing rule.
"""

from __future__ import annotations

import re

from .profile_updater import PROFILE_FIELDS, UserProfile, is_clear_lexical_overlap

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "i", "if", "in", "is", "it", "its", "of",
    "on", "or", "so", "that", "the", "this", "to", "was", "were", "with",
    "you", "your",
}


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if token not in _STOPWORDS and len(token) > 1
    }


def is_more_informative_overlap(candidate: str, other: str) -> bool:
    """Return True only when candidate safely dominates overlapping ``other``.

    The relation is intentionally directional. Merely being similar is not
    enough. The retained candidate must contain the omitted normalized phrase,
    or its content-token set must be a strict superset of the omitted entry's
    content-token set. This blocks deletion of a richer sentence in favor of a
    shorter fragment.
    """

    if candidate == other or not is_clear_lexical_overlap(candidate, other):
        return False

    candidate_norm = _normalize(candidate)
    other_norm = _normalize(other)
    if not candidate_norm or not other_norm:
        return False

    if other_norm in candidate_norm and len(candidate_norm) > len(other_norm):
        return True

    candidate_tokens = _content_tokens(candidate)
    other_tokens = _content_tokens(other)
    return bool(other_tokens) and other_tokens < candidate_tokens


def apply_retention_guard(
    model_selected: UserProfile,
    *,
    allowed_profile: UserProfile,
) -> tuple[UserProfile, dict[str, list[str]], dict[str, list[str]]]:
    """Build a safe profile while preserving the richer overlap representative.

    1. Exact duplicate input strings collapse naturally to one occurrence.
    2. A model-omitted unique entry is deleted only when a selected same-category
       entry strictly dominates it under ``is_more_informative_overlap``.
    3. Otherwise the omitted entry is restored.
    4. After restoration, any shorter entry strictly dominated by another safe
       entry is removed deterministically, independent of the model's direction.

    Returns ``(safe_profile, restored_entries, allowed_removals)``.
    """

    safe_fields: dict[str, tuple[str, ...]] = {}
    restored: dict[str, list[str]] = {field: [] for field in PROFILE_FIELDS}
    allowed_removals: dict[str, list[str]] = {field: [] for field in PROFILE_FIELDS}

    for field_name in PROFILE_FIELDS:
        original_values = list(getattr(allowed_profile, field_name))
        unique_original = list(dict.fromkeys(original_values))
        selected_values = list(dict.fromkeys(getattr(model_selected, field_name)))
        selected_set = set(selected_values)

        preliminary: list[str] = []
        for value in unique_original:
            if value in selected_set:
                preliminary.append(value)
                continue

            selected_dominators = [
                kept
                for kept in selected_values
                if kept != value and is_more_informative_overlap(kept, value)
            ]
            if selected_dominators:
                allowed_removals[field_name].append(value)
            else:
                preliminary.append(value)
                restored[field_name].append(value)

        # Direction-independent safety pass: if the model kept a short overlap
        # but omitted a richer one, the richer item was restored above. Remove
        # the dominated short representative now so compaction does not lose
        # information.
        final_values: list[str] = []
        for value in preliminary:
            dominators = [
                other
                for other in preliminary
                if other != value and is_more_informative_overlap(other, value)
            ]
            if dominators:
                if value not in allowed_removals[field_name]:
                    allowed_removals[field_name].append(value)
                continue
            final_values.append(value)

        safe_fields[field_name] = tuple(final_values)

    return (
        UserProfile(
            likes=safe_fields["likes"],
            dislikes=safe_fields["dislikes"],
            key_features=safe_fields["key_features"],
        ),
        restored,
        allowed_removals,
    )
