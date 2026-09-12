"""Rank-map serialization for PURE STEP 3 candidate ranking.

The direct ranking-array protocol was closest to the paper but produced two
malformed 20-item permutations in the first full run. A score-based fallback
covered all candidates reliably, but the pilot collapsed many candidates to the
same score, so arbitrary frozen candidate order determined a large fraction of
the final ranking.

This module tests a third serialization that stays closer to the paper's ranking
objective while avoiding a unique array constraint: the model assigns each
numbered candidate an explicit rank position 1..20. JSON Schema can require all
candidate keys individually. The parser then enforces that the rank values form
an exact permutation of 1..20. No duplicate rank, missing rank, candidate repair,
or tie-breaking is allowed.

This is an explicit reproduction engineering choice because the PURE paper does
not publish its machine-readable output schema.
"""

from __future__ import annotations

import json
from typing import Mapping, Sequence

from .profile_updater import UserProfile
from .recommender import PAPER_RECOMMENDER_INSTRUCTION, SYSTEM_PROMPT


def pure_recommender_rankmap_response_format(candidate_count: int) -> dict[str, object]:
    """Return a strict schema requiring one integer rank for every candidate."""

    if candidate_count < 1:
        raise ValueError("candidate_count must be >= 1")

    candidate_keys = [str(index) for index in range(1, candidate_count + 1)]
    rank_properties = {
        key: {
            "type": "integer",
            "minimum": 1,
            "maximum": candidate_count,
        }
        for key in candidate_keys
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "pure_candidate_rank_map",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "ranks": {
                        "type": "object",
                        "properties": rank_properties,
                        "required": candidate_keys,
                        "additionalProperties": False,
                    }
                },
                "required": ["ranks"],
                "additionalProperties": False,
            },
        },
    }


def build_pure_recommender_rankmap_messages(
    *,
    history: Sequence[Mapping[str, object]],
    profile: UserProfile,
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build a leakage-safe rank-map request for PURE recommendation."""

    if not history:
        raise ValueError("PURE recommender requires at least one observed purchase")
    if not candidate_asins:
        raise ValueError("candidate_asins must not be empty")
    if len(set(candidate_asins)) != len(candidate_asins):
        raise ValueError("candidate_asins must be unique")
    if len(candidate_asins) != 20:
        raise ValueError(f"Paper evaluation uses 20 candidates; received {len(candidate_asins)}")

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

    profile_payload = profile.to_dict()
    paper_instruction = PAPER_RECOMMENDER_INSTRUCTION.format(
        likes=json.dumps(profile_payload["likes"], ensure_ascii=False),
        dislikes=json.dumps(profile_payload["dislikes"], ensure_ascii=False),
        key_features=json.dumps(profile_payload["key_features"], ensure_ascii=False),
        candidate_list="candidate list",
    )

    candidate_keys = [str(index) for index in range(1, len(candidate_asins) + 1)]
    user_prompt = (
        "Purchased items in chronological order (oldest to newest):\n"
        + "\n".join(history_lines)
        + "\n\nCurrent PURE user profile:\n"
        + paper_instruction
        + "\n\nNumbered candidate list:\n"
        + "\n".join(candidate_lines)
        + "\n\nFor machine-readable serialization, assign EVERY candidate exactly one UNIQUE rank "
        f"from 1 through {len(candidate_asins)}, where rank 1 is the most likely next purchase "
        f"and rank {len(candidate_asins)} is the least likely. Use every rank value exactly once.\n"
        "Return exactly one JSON object with exactly one key named `ranks`. The value of `ranks` "
        "must be an object containing exactly these candidate-number keys: "
        + ", ".join(candidate_keys)
        + ". Each key's integer value is that candidate's rank position. Do not return a ranking "
        "array, scores, product names, ASINs, explanations, Markdown, duplicate rank values, "
        "missing keys, missing ranks, or extra keys."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def parse_candidate_rankmap(
    text: str,
    candidate_asins: Sequence[str],
) -> tuple[list[str], dict[int, int]]:
    """Parse an exact candidate->rank permutation and return the ranked ASIN list.

    The parser is deliberately strict. Every candidate-number key 1..N must be
    present exactly once, every value must be an integer in 1..N, and the set of
    rank values must equal 1..N. There is no semantic or structural repair.
    """

    if not candidate_asins:
        raise ValueError("candidate_asins must not be empty")
    if len(set(candidate_asins)) != len(candidate_asins):
        raise ValueError("candidate_asins must be unique")

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

    if not isinstance(payload, dict) or set(payload) != {"ranks"}:
        raise ValueError("Rank-map response must contain exactly one top-level key named `ranks`")
    raw_ranks = payload["ranks"]
    if not isinstance(raw_ranks, dict):
        raise ValueError("`ranks` must be a JSON object")

    candidate_count = len(candidate_asins)
    expected_keys = {str(index) for index in range(1, candidate_count + 1)}
    actual_keys = set(raw_ranks)
    missing_keys = sorted(expected_keys - actual_keys, key=int)
    extra_keys = sorted(actual_keys - expected_keys)
    if missing_keys or extra_keys:
        raise ValueError(f"Rank-map keys mismatch; missing={missing_keys}, extra={extra_keys}")

    ranks: dict[int, int] = {}
    for number in range(1, candidate_count + 1):
        raw_value = raw_ranks[str(number)]
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise ValueError(f"Candidate {number} rank must be an integer")
        if raw_value < 1 or raw_value > candidate_count:
            raise ValueError(
                f"Candidate {number} rank {raw_value} outside [1, {candidate_count}]"
            )
        ranks[number] = raw_value

    expected_rank_values = set(range(1, candidate_count + 1))
    actual_rank_values = set(ranks.values())
    duplicates = sorted(
        rank for rank in actual_rank_values if list(ranks.values()).count(rank) > 1
    )
    missing_rank_values = sorted(expected_rank_values - actual_rank_values)
    if duplicates or missing_rank_values or len(actual_rank_values) != candidate_count:
        raise ValueError(
            "Rank values are not a complete permutation; "
            f"duplicates={duplicates}, missing={missing_rank_values}"
        )

    ranking_numbers = sorted(ranks, key=lambda number: ranks[number])
    ranking = [candidate_asins[number - 1] for number in ranking_numbers]
    return ranking, ranks
