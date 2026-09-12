"""Rank-map fallback serialization for the Recency-Focused baseline.

This module preserves the exact semantic inputs of the Recency-Focused method:
chronological purchase-history titles, explicit emphasis on the latest observed
purchase, and the frozen numbered candidate titles. It is used only after the
direct ranking-array response fails strict structural validation.

Only output serialization changes. Every candidate receives one explicit rank
position and the shared strict rank-map parser requires a complete permutation.
No candidate is inserted, deleted, inferred, reordered, or repaired after model
generation.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .recency import SYSTEM_PROMPT


def build_recency_rankmap_messages(
    history: Sequence[Mapping[str, object]],
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build one fresh rank-map fallback request for Recency-Focused."""

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
    candidate_keys = [str(index) for index in range(1, candidate_count + 1)]

    user_prompt = (
        "Purchase history in chronological order (oldest to newest). This section is context only:\n"
        + "\n".join(history_lines)
        + f"\n\nNote that my most recently purchased item is: {recent_title}. "
        "Give this recent purchase special emphasis when estimating my next purchase.\n"
        + "\nNumbered candidate products:\n"
        + "\n".join(candidate_lines)
        + "\n\nRank ONLY the numbered candidate products from most likely to least likely to be the next purchase.\n"
        + f"For machine-readable serialization, assign EVERY candidate exactly one UNIQUE rank from 1 through {candidate_count}, "
        + f"where rank 1 is most likely and rank {candidate_count} is least likely. Use every rank value exactly once.\n"
        + "Return exactly one JSON object with exactly one key named `ranks`. The value of `ranks` must be an object containing exactly these candidate-number keys: "
        + ", ".join(candidate_keys)
        + ". Each key's integer value is that candidate's rank position. "
        + "Do not return a ranking array, product names, ASINs, purchase-history numbers, explanations, Markdown, duplicate rank values, missing keys, missing ranks, placeholders, ellipses, or extra keys."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


__all__ = ["build_recency_rankmap_messages"]
