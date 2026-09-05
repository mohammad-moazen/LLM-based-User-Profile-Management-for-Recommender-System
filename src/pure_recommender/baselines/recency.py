"""Recency-focused LLM baseline for the PURE evaluation setup.

The paper defines Recency-Focused as the Sequential baseline plus an explicit
instruction emphasizing the most recently purchased item at time step t-1.

This implementation preserves the validated numbered-candidate serialization
used by our Sequential baseline: purchase history and candidate titles are shown
to the model, ASINs remain hidden from the prompt, and the model ranks only
candidate numbers 1..N. The ranked numbers are mapped back to the unchanged
frozen candidate ASIN list by the shared parser.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .sequential import parse_complete_ranking, target_rank


SYSTEM_PROMPT = (
    "You are a recommender system. Use the chronological purchase history as context, "
    "with special emphasis on the user's most recent purchase. Rank ONLY the numbered "
    "candidate products. Never include purchase-history entries in the ranking."
)


def build_recency_messages(
    history: Sequence[Mapping[str, object]],
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build the Recency-Focused baseline prompt.

    Relative to Sequential, the only behavioral change is an explicit note that
    identifies the last observed purchase as the most recent item and asks the
    model to emphasize it when ranking the next-purchase candidates.
    """

    if not history:
        raise ValueError("Recency baseline requires at least one observed purchase")
    if not candidate_asins:
        raise ValueError("candidate_asins must not be empty")
    if len(set(candidate_asins)) != len(candidate_asins):
        raise ValueError("candidate_asins must be unique")

    history_lines: list[str] = []
    for index, row in enumerate(history, start=1):
        title = str(row.get("title", "")).strip()
        if not title:
            raise ValueError(f"Invalid history row: {row!r}")
        history_lines.append(f"{index}. {title}")

    recent_title = str(history[-1].get("title", "")).strip()
    if not recent_title:
        raise ValueError("Most recent history row is missing a title")

    candidate_lines: list[str] = []
    for index, asin in enumerate(candidate_asins, start=1):
        title = item_titles.get(asin)
        if not title:
            raise ValueError(f"Missing canonical title for candidate ASIN {asin!r}")
        candidate_lines.append(f"Candidate {index}: {title}")

    candidate_count = len(candidate_asins)
    user_prompt = (
        "Purchase history in chronological order (oldest to newest). This section is context only:\n"
        + "\n".join(history_lines)
        + f"\n\nNote that my most recently purchased item is: {recent_title}. "
        "Give this recent purchase special emphasis when estimating my next purchase.\n"
        + "\nNumbered candidate products:\n"
        + "\n".join(candidate_lines)
        + "\n\nRank ONLY the numbered candidate products from most likely to least likely to be the next purchase.\n"
        "Return exactly one valid JSON object and no explanation or Markdown.\n"
        "The JSON object must contain exactly one key named `ranking`.\n"
        f"The `ranking` value must contain exactly {candidate_count} candidate numbers.\n"
        f"Use every integer from 1 through {candidate_count} exactly once.\n"
        "Do not return product names, ASINs, purchase-history numbers, placeholders, or ellipses.\n"
        "No omissions, no duplicates, and no extra values.\n"
        f"Before answering, verify that the array is a complete permutation of the integers 1 through {candidate_count}."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


__all__ = [
    "SYSTEM_PROMPT",
    "build_recency_messages",
    "parse_complete_ranking",
    "target_rank",
]
