"""Prompt construction for PURE STEP 3: Recommend Next Purchase Item.

The paper publishes this recommender prompt template:

    Positive aspects: {likes} Negative aspects: {dislikes} Key Features:
    {key features} Based on these inputs, rank the {candidate list} from 1 to 20
    by evaluating their likelihood of being purchased.

Algorithm 1 and the accompanying prose also define the recommender as using the
updated profile together with purchased items I^t_u and the candidate set. The
published template does not show exactly how I^t_u is serialized. This
reproduction therefore prepends the chronological purchased-item titles and then
uses the published profile/candidate instruction. This choice is explicit and
keeps the final PURE method consistent with Algorithm 1 and the component table.

Candidates use the already-frozen numbered-title interface from Phase 2. ASINs
are hidden from the model and mapped back deterministically after parsing.
"""

from __future__ import annotations

import json
from typing import Mapping, Sequence

from .profile_updater import UserProfile


PAPER_RECOMMENDER_INSTRUCTION = (
    "Positive aspects: {likes} Negative aspects: {dislikes} Key Features: {key_features} "
    "Based on these inputs, rank the {candidate_list} from 1 to 20 by evaluating "
    "their likelihood of being purchased."
)

SYSTEM_PROMPT = (
    "You are the Recommender component of the PURE recommendation framework. "
    "Use the chronological purchase history and the current leakage-safe user profile "
    "to rank only the numbered candidate products by likelihood of next purchase."
)


def pure_recommender_response_format(candidate_count: int) -> dict[str, object]:
    """Return a strict JSON schema for a complete numbered-candidate ranking."""

    if candidate_count < 1:
        raise ValueError("candidate_count must be >= 1")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "pure_candidate_ranking",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "ranking": {
                        "type": "array",
                        "items": {
                            "type": "integer",
                            "enum": list(range(1, candidate_count + 1)),
                        },
                        "minItems": candidate_count,
                        "maxItems": candidate_count,
                        "uniqueItems": True,
                    }
                },
                "required": ["ranking"],
                "additionalProperties": False,
            },
        },
    }


def build_pure_recommender_messages(
    *,
    history: Sequence[Mapping[str, object]],
    profile: UserProfile,
    candidate_asins: Sequence[str],
    item_titles: Mapping[str, str],
) -> list[dict[str, str]]:
    """Build one leakage-safe PURE recommender request.

    History order is oldest to newest. The profile must already be the Phase 4
    state after the latest observed purchase and therefore must not contain any
    target or future review. Candidate order is the frozen Phase 1 order.
    """

    if not history:
        raise ValueError("PURE recommender requires at least one observed purchase")
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

    profile_payload = profile.to_dict()
    candidate_count = len(candidate_asins)
    if candidate_count != 20:
        raise ValueError(
            f"Paper evaluation uses 20 candidates; received {candidate_count}"
        )

    paper_instruction = PAPER_RECOMMENDER_INSTRUCTION.format(
        likes=json.dumps(profile_payload["likes"], ensure_ascii=False),
        dislikes=json.dumps(profile_payload["dislikes"], ensure_ascii=False),
        key_features=json.dumps(profile_payload["key_features"], ensure_ascii=False),
        candidate_list="candidate list",
    )

    user_prompt = (
        "Purchased items in chronological order (oldest to newest):\n"
        + "\n".join(history_lines)
        + "\n\nCurrent PURE user profile:\n"
        + paper_instruction
        + "\n\nNumbered candidate list:\n"
        + "\n".join(candidate_lines)
        + "\n\nReturn exactly one JSON object with exactly one key named `ranking`. "
        f"The ranking must contain every integer from 1 through {candidate_count} exactly once, "
        "ordered from most likely to least likely next purchase. Return no explanation, "
        "product names, ASINs, Markdown, duplicates, omissions, or extra values."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
