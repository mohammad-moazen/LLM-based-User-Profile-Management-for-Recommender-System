"""In-Context Learning (ICL) baseline for the PURE evaluation setup.

The PURE paper describes ICL differently from Sequential and Recency-Focused:
for prediction at time step t, the prompt uses user-item interactions only up to
t-2 and treats the purchase at t-1 as an in-context demonstrated outcome. The
paper's additional prompt conceptually says that, after the earlier purchases,
the recommender should have recommended the recent item, and now that the user
has bought that recent item it should predict the next purchase.

This implementation preserves the numbered-candidate serialization already
validated by the Sequential and Recency-Focused local runs. Product titles carry
semantic information; ASINs remain internal; current candidates are numbered
1..N; and the shared parser maps the model's ranked numbers back to the unchanged
frozen candidate ASIN list.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .sequential import parse_complete_ranking, target_rank


SYSTEM_PROMPT = (
    "You are a recommender system using in-context learning. Learn from the user's "
    "earlier purchase history and the demonstrated recent purchase outcome. Rank ONLY "
    "the numbered current candidate products. Never include purchase-history entries "
    "or the demonstrated recent item as ranking outputs unless they are independently "
    "present among the numbered current candidates."
)


def build_icl_messages(
    history: Sequence[Mapping[str, object]],
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build the ICL baseline prompt for one current recommendation session.

    ``history`` contains all observed purchases through t-1. Following the paper:
    - rows ``history[:-1]`` are the earlier interactions through t-2;
    - ``history[-1]`` is the recent purchase at t-1 and is presented as an
      in-context demonstrated recommendation outcome;
    - the current candidate list is the frozen candidate set for target t.

    Reviews, ratings, timestamps, ASINs, and future information are excluded.
    """

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
    user_prompt = (
        "Earlier purchase history through time step t-2 (oldest to newest):\n"
        + "\n".join(earlier_lines)
        + "\n\nIn-context demonstration:\n"
        + f"After those earlier purchases, the item you should have recommended to me was: {recent_title}.\n"
        + f"Now that I have bought {recent_title}, predict my next purchase from the current candidates below.\n"
        + "\nCurrent numbered candidate products:\n"
        + "\n".join(candidate_lines)
        + "\n\nRank ONLY the current numbered candidate products from most likely to least likely to be the next purchase.\n"
        "Return exactly one valid JSON object and no explanation or Markdown.\n"
        "The JSON object must contain exactly one key named `ranking`.\n"
        f"The `ranking` value must contain exactly {candidate_count} candidate numbers.\n"
        f"Use every integer from 1 through {candidate_count} exactly once.\n"
        "Do not return product names, ASINs, history numbers, placeholders, or ellipses.\n"
        "No omissions, no duplicates, and no extra values.\n"
        f"Before answering, verify that the array is a complete permutation of the integers 1 through {candidate_count}."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


__all__ = [
    "SYSTEM_PROMPT",
    "build_icl_messages",
    "parse_complete_ranking",
    "target_rank",
]
