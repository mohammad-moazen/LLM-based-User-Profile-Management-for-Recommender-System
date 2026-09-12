"""Rank-map fallback serialization for the ICL baseline.

This preserves the ICL semantics: earlier interactions through t-2 are context,
the purchase at t-1 is shown as an in-context demonstrated outcome, and only the
current frozen candidate titles are ranked. It is used only after the direct
ranking-array response fails strict structural validation.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .icl import SYSTEM_PROMPT


def build_icl_rankmap_messages(
    history: Sequence[Mapping[str, object]],
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    if len(history) < 2:
        raise ValueError("ICL baseline requires at least two observed purchases")
    if not candidate_asins:
        raise ValueError("candidate_asins must not be empty")
    if len(set(candidate_asins)) != len(candidate_asins):
        raise ValueError("candidate_asins must be unique")

    earlier_history = history[:-1]
    recent_row = history[-1]

    earlier_lines: list[str] = []
    for index, row in enumerate(earlier_history, start=1):
        title = str(row.get("title", "")).strip()
        if not title:
            raise ValueError(f"Invalid earlier-history row: {row!r}")
        earlier_lines.append(f"{index}. {title}")

    recent_title = str(recent_row.get("title", "")).strip()
    if not recent_title:
        raise ValueError("Recent t-1 history row is missing a title")

    candidate_lines: list[str] = []
    for index, asin in enumerate(candidate_asins, start=1):
        title = item_titles.get(asin)
        if not title:
            raise ValueError(f"Missing canonical title for candidate ASIN {asin!r}")
        candidate_lines.append(f"Candidate {index}: {title}")

    candidate_count = len(candidate_asins)
    candidate_keys = [str(index) for index in range(1, candidate_count + 1)]

    user_prompt = (
        "Earlier purchase history through time step t-2 (oldest to newest):\n"
        + "\n".join(earlier_lines)
        + "\n\nIn-context demonstration:\n"
        + f"After those earlier purchases, the item you should have recommended to me was: {recent_title}.\n"
        + f"Now that I have bought {recent_title}, predict my next purchase from the current candidates below.\n"
        + "\nCurrent numbered candidate products:\n"
        + "\n".join(candidate_lines)
        + "\n\nRank ONLY the current numbered candidate products from most likely to least likely to be the next purchase.\n"
        + f"For machine-readable serialization, assign EVERY candidate exactly one UNIQUE rank from 1 through {candidate_count}, "
        + f"where rank 1 is most likely and rank {candidate_count} is least likely. Use every rank value exactly once.\n"
        + "Return exactly one JSON object with exactly one key named `ranks`. The value of `ranks` must be an object containing exactly these candidate-number keys: "
        + ", ".join(candidate_keys)
        + ". Each key's integer value is that candidate's rank position. "
        + "Do not return a ranking array, product names, ASINs, history numbers, explanations, Markdown, duplicate rank values, missing keys, missing ranks, placeholders, ellipses, or extra keys."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


__all__ = ["build_icl_rankmap_messages"]
