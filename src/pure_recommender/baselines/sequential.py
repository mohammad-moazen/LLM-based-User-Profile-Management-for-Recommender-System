"""Paper-aligned Sequential baseline prompt construction and ranking parsing.

The PURE paper describes the Sequential baseline as providing only the user's
chronological user-item interactions and the candidate list, then asking the
LLM to rank candidates by likelihood of purchase. The paper does not publish an
exact Sequential prompt template or a JSON schema, so this module makes those
reproduction choices explicit and deliberately minimal.

Important constraints enforced here:
- purchase history only: no reviews, ratings, profiles, or future items;
- every candidate is shown exactly once;
- the ground-truth target is never marked or described as the target;
- purchase history is context only and can never be emitted as a candidate;
- output must contain a complete permutation of numbered candidate positions.

Why numbered candidates instead of ASIN output?
The first real local-model pilot showed that a small model can copy ASINs from
both the purchase history and candidate list into the ranking even when asked to
rank candidates only. ASINs carry no useful semantic meaning for recommendation;
product titles do. We therefore expose history titles as context, expose candidate
titles with stable local numbers 1..N, and ask the model to rank only those
numbers. The parser then maps the ranked numbers back to the frozen ASIN list.
This is a formatting/serialization choice, not a change to the candidate set or
evaluation target.
"""

from __future__ import annotations

import json
from typing import Mapping, Sequence


SYSTEM_PROMPT = (
    "You are a recommender system. Use the chronological purchase history only as context. "
    "Rank ONLY the numbered candidate products. Never include purchase-history entries in the ranking."
)


def build_sequential_messages(
    history: Sequence[Mapping[str, object]],
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build the minimal Sequential-baseline chat messages.

    Product titles provide the semantic information available to the LLM. ASINs
    are deliberately hidden from the prompt because they are machine identifiers,
    not semantic features, and the local 3B pilot copied history ASINs into the
    candidate ranking. Candidates are instead assigned stable prompt-local
    numbers 1..N, which are mapped back to the frozen ASIN order after parsing.
    History order remains oldest -> newest.
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
    user_prompt = (
        "Purchase history in chronological order (oldest to newest). This section is context only:\n"
        + "\n".join(history_lines)
        + "\n\nNumbered candidate products:\n"
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


def _extract_json_object(text: str) -> dict[str, object]:
    """Extract one JSON object, tolerating a surrounding Markdown code fence."""

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
        raise ValueError("Model response does not contain a JSON object")

    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model response contains invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Ranking response must be a JSON object")
    return payload


def _normalize_candidate_number(value: object) -> int:
    """Normalize an integer or a digit-only JSON string to one candidate number.

    Accepting a quoted number is a serialization tolerance only; it does not
    repair, infer, add, remove, or reorder any candidate choice.
    """

    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid candidate numbers")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError(f"Invalid candidate number in ranking: {value!r}")


def parse_complete_ranking(text: str, candidate_asins: Sequence[str]) -> list[str]:
    """Parse a complete candidate-number permutation and map it back to ASINs."""

    expected_asins = list(candidate_asins)
    payload = _extract_json_object(text)
    raw_ranking = payload.get("ranking")
    if not isinstance(raw_ranking, list):
        raise ValueError("JSON response must contain an array field named `ranking`")

    ranking_numbers = [_normalize_candidate_number(value) for value in raw_ranking]
    candidate_count = len(expected_asins)
    if len(ranking_numbers) != candidate_count:
        raise ValueError(
            f"Ranking length {len(ranking_numbers)} does not match candidate count {candidate_count}"
        )
    if len(set(ranking_numbers)) != len(ranking_numbers):
        raise ValueError("Ranking contains duplicate candidate numbers")

    expected_numbers = set(range(1, candidate_count + 1))
    actual_numbers = set(ranking_numbers)
    missing = sorted(expected_numbers - actual_numbers)
    unexpected = sorted(actual_numbers - expected_numbers)
    if missing or unexpected:
        raise ValueError(
            "Ranking is not a permutation of candidate numbers; "
            f"missing={missing}, unexpected={unexpected}"
        )

    return [expected_asins[number - 1] for number in ranking_numbers]


def target_rank(ranking: Sequence[str], target_asin: str) -> int:
    """Return the 1-based position of the ground-truth ASIN."""

    try:
        return list(ranking).index(target_asin) + 1
    except ValueError as exc:
        raise ValueError(f"Target ASIN {target_asin!r} is absent from ranking") from exc
