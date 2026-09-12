"""Score-based serialization for PURE STEP 3 candidate ranking.

The accepted Phase 5 pilot asked the local model to emit one complete permutation
of candidate numbers 1..20. In the first 94-session run the LM Studio backend
returned two arrays that violated JSON Schema ``uniqueItems`` by repeating one
candidate number and omitting another. A deterministic formatting-only retry with
the same model, temperature, seed, prompt context, and schema reproduced the same
invalid arrays for both failures.

The PURE paper specifies the recommendation task (rank 20 candidates by purchase
likelihood) but does not publish a machine-readable output schema. This module
therefore introduces an explicit reproduction serialization choice: ask the model
to assign an integer purchase-likelihood score to every numbered candidate, then
sort those scores deterministically. Required object keys make coverage of all 20
candidates enforceable without relying on cross-item ``uniqueItems`` behavior.

No candidate is inserted, deleted, semantically repaired, or rescored after model
generation. Ties are resolved by frozen candidate number (ascending), which is a
deterministic formatting rule over the already-randomized frozen candidate order.
"""

from __future__ import annotations

from collections import Counter
import json
from typing import Mapping, Sequence

from .profile_updater import UserProfile
from .recommender import PAPER_RECOMMENDER_INSTRUCTION, SYSTEM_PROMPT


SCORE_MIN = 0
SCORE_MAX = 1000


def pure_recommender_score_response_format(candidate_count: int) -> dict[str, object]:
    """Return a strict schema requiring one integer score for every candidate."""

    if candidate_count < 1:
        raise ValueError("candidate_count must be >= 1")

    candidate_keys = [str(index) for index in range(1, candidate_count + 1)]
    score_properties = {
        key: {
            "type": "integer",
            "minimum": SCORE_MIN,
            "maximum": SCORE_MAX,
        }
        for key in candidate_keys
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "pure_candidate_purchase_likelihood_scores",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "scores": {
                        "type": "object",
                        "properties": score_properties,
                        "required": candidate_keys,
                        "additionalProperties": False,
                    }
                },
                "required": ["scores"],
                "additionalProperties": False,
            },
        },
    }


def build_pure_recommender_score_messages(
    *,
    history: Sequence[Mapping[str, object]],
    profile: UserProfile,
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build a leakage-safe score-serialization request for the PURE ranker."""

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
        + "\n\nFor machine-readable serialization, assign EVERY candidate an integer purchase-likelihood "
        f"score from {SCORE_MIN} through {SCORE_MAX}, where a larger score means more likely to be "
        "the next purchase. Evaluate the same ranking task described above; do not introduce any new "
        "information. Scores may tie.\n"
        "Return exactly one JSON object with exactly one key named `scores`. The value of `scores` "
        "must be an object containing exactly these candidate-number keys: "
        + ", ".join(candidate_keys)
        + ". Return every key exactly once. Do not return a ranking array, product names, ASINs, "
        "explanations, Markdown, missing keys, or extra keys."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def parse_candidate_scores(
    text: str,
    candidate_asins: Sequence[str],
) -> tuple[list[str], dict[int, int], int, int]:
    """Parse complete candidate scores and derive a deterministic full ranking.

    Returns ``(ranking_asins, scores_by_candidate_number, tie_group_count,
    tied_candidate_count)``. Higher scores rank first. Exact score ties are broken
    by frozen candidate number ascending.
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

    if not isinstance(payload, dict) or set(payload) != {"scores"}:
        raise ValueError("Score response must contain exactly one top-level key named `scores`")
    raw_scores = payload["scores"]
    if not isinstance(raw_scores, dict):
        raise ValueError("`scores` must be a JSON object")

    candidate_count = len(candidate_asins)
    expected_keys = {str(index) for index in range(1, candidate_count + 1)}
    actual_keys = set(raw_scores)
    missing = sorted(expected_keys - actual_keys, key=int)
    extra = sorted(actual_keys - expected_keys)
    if missing or extra:
        raise ValueError(f"Score keys mismatch; missing={missing}, extra={extra}")

    scores: dict[int, int] = {}
    for number in range(1, candidate_count + 1):
        raw_value = raw_scores[str(number)]
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise ValueError(f"Candidate {number} score must be an integer")
        if raw_value < SCORE_MIN or raw_value > SCORE_MAX:
            raise ValueError(
                f"Candidate {number} score {raw_value} outside [{SCORE_MIN}, {SCORE_MAX}]"
            )
        scores[number] = raw_value

    ranking_numbers = sorted(scores, key=lambda number: (-scores[number], number))
    ranking = [candidate_asins[number - 1] for number in ranking_numbers]

    score_counts = Counter(scores.values())
    tie_sizes = [count for count in score_counts.values() if count > 1]
    tie_group_count = len(tie_sizes)
    tied_candidate_count = sum(tie_sizes)
    return ranking, scores, tie_group_count, tied_candidate_count
