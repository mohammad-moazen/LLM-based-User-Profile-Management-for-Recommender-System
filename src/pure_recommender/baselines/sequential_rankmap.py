"""Rank-map fallback serialization for the Sequential baseline.

The final PURE evaluation adopted a hybrid output policy because the local LM
Studio backend occasionally emitted malformed ranking arrays despite a strict
JSON schema. For the final thesis comparison, baseline methods must use the same
mechanical output policy so that a method is not advantaged or penalized by a
different serialization contract.

This module does NOT change the Sequential recommendation information available
to the model. It uses exactly the same chronological purchase-history titles and
frozen numbered candidate titles as ``build_sequential_messages``. The only
change is the machine-readable output form used after a direct ranking-array
response has already failed strict structural validation.

The model assigns every candidate-number key an explicit rank position 1..N.
The shared strict rank-map parser then requires those values to be an exact
permutation. No candidate is inserted, deleted, inferred, reordered, or repaired
post-generation.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .sequential import SYSTEM_PROMPT


def build_sequential_rankmap_messages(
    history: Sequence[Mapping[str, object]],
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build the fresh rank-map fallback request for Sequential.

    The semantic task and visible evidence are deliberately identical to the
    direct Sequential request:
    - only observed purchases strictly before the target are shown;
    - history is chronological, oldest to newest;
    - candidate titles are shown under stable prompt-local numbers;
    - ASINs, reviews, ratings, profiles, targets, and future interactions remain
      hidden from the model.

    Only the output serialization differs. Every candidate gets one explicit rank
    position, and the downstream parser rejects duplicate/missing rank values.
    """

    if not history:
        raise ValueError("Sequential baseline requires at least one observed purchase")
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
        + "\n\nNumbered candidate products:\n"
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


__all__ = ["build_sequential_rankmap_messages"]
