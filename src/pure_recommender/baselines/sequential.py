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
- output must contain a complete permutation of candidate ASINs.
"""

from __future__ import annotations

import json
from typing import Mapping, Sequence


SYSTEM_PROMPT = (
    "You are a recommender system. Rank candidate products using only the user's "
    "chronological purchase history. Do not invent products and do not omit candidates."
)


def build_sequential_messages(
    history: Sequence[Mapping[str, object]],
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build the minimal Sequential-baseline chat messages.

    ASINs are included as stable machine-readable identifiers. Product titles
    carry the semantic information available to the LLM. The history order is
    oldest -> newest, matching the continuous sequential setup.
    """

    if not history:
        raise ValueError("Sequential baseline requires at least one observed purchase")
    if not candidate_asins:
        raise ValueError("candidate_asins must not be empty")
    if len(set(candidate_asins)) != len(candidate_asins):
        raise ValueError("candidate_asins must be unique")

    history_lines: list[str] = []
    for index, row in enumerate(history, start=1):
        asin = str(row.get("asin", "")).strip()
        title = str(row.get("title", "")).strip()
        if not asin or not title:
            raise ValueError(f"Invalid history row: {row!r}")
        history_lines.append(f"{index}. {title} [{asin}]")

    candidate_lines: list[str] = []
    for index, asin in enumerate(candidate_asins, start=1):
        title = item_titles.get(asin)
        if not title:
            raise ValueError(f"Missing canonical title for candidate ASIN {asin!r}")
        candidate_lines.append(f"{index}. {title} [{asin}]")

    user_prompt = (
        "I've purchased the following products in chronological order (oldest to newest):\n"
        + "\n".join(history_lines)
        + "\n\nCandidate products:\n"
        + "\n".join(candidate_lines)
        + "\n\nRank ALL candidate products from most likely to least likely to be my next purchase. "
        "Return exactly one valid JSON object and no explanation. Use this schema:\n"
        '{"ranking":["ASIN_1","ASIN_2",...,"ASIN_N"]}\n'
        "The ranking array must contain every candidate ASIN exactly once."
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


def parse_complete_ranking(text: str, candidate_asins: Sequence[str]) -> list[str]:
    """Parse and validate a complete permutation of the candidate ASINs."""

    expected = list(candidate_asins)
    payload = _extract_json_object(text)
    ranking = payload.get("ranking")
    if not isinstance(ranking, list) or not all(isinstance(value, str) for value in ranking):
        raise ValueError("JSON response must contain a string-array field named `ranking`")

    normalized = [value.strip() for value in ranking]
    if len(normalized) != len(expected):
        raise ValueError(
            f"Ranking length {len(normalized)} does not match candidate count {len(expected)}"
        )
    if len(set(normalized)) != len(normalized):
        raise ValueError("Ranking contains duplicate ASINs")

    expected_set = set(expected)
    actual_set = set(normalized)
    missing = sorted(expected_set - actual_set)
    unexpected = sorted(actual_set - expected_set)
    if missing or unexpected:
        raise ValueError(
            f"Ranking is not a permutation of candidates; missing={missing}, unexpected={unexpected}"
        )
    return normalized


def target_rank(ranking: Sequence[str], target_asin: str) -> int:
    """Return the 1-based position of the ground-truth ASIN."""

    try:
        return list(ranking).index(target_asin) + 1
    except ValueError as exc:
        raise ValueError(f"Target ASIN {target_asin!r} is absent from ranking") from exc
