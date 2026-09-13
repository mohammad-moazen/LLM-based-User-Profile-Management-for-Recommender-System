"""Conservative fallback helpers for Phase 10B2 Profile Updater.

The fallback is used only when the primary LLM updater cannot produce a usable
state (for example because the prompt exceeds the frozen 8192-token context or
all fresh structured-output attempts fail). It preserves all distinct evidence
by treating the concatenated profile as selected, then applies the already
accepted information-preserving retention guard v4. Therefore it can reduce
compaction, but it does not discard unique preference evidence.
"""

from __future__ import annotations

from pure_recommender.pure import UserProfile, apply_retention_guard

FALLBACK_POLICY = "preserve_all_then_guard_v4"


def is_context_overflow_error(exc: BaseException | str) -> bool:
    """Return True for the local-server context-size failure seen in Phase 10B2."""

    text = str(exc).casefold()
    markers = (
        "exceed_context_size_error",
        "exceeds the available context size",
        "n_ctx",
    )
    return any(marker in text for marker in markers)


def conservative_fallback_profile(
    concatenated: UserProfile,
) -> tuple[UserProfile, dict[str, list[str]], dict[str, list[str]]]:
    """Preserve all evidence and apply only the frozen deterministic guard.

    Passing the exact concatenated profile as ``model_selected`` means the guard
    never interprets a failed model response. Exact duplicates and strictly
    dominated overlaps may still be compacted by guard v4, exactly as in the
    accepted Phase 4 safety policy.
    """

    return apply_retention_guard(
        concatenated,
        allowed_profile=concatenated,
    )


__all__ = [
    "FALLBACK_POLICY",
    "conservative_fallback_profile",
    "is_context_overflow_error",
]
