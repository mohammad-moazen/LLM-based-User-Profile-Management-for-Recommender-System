"""PURE Review Extractor prompt, schema, and strict parser.

The paper's Algorithm 1 applies the extractor to the incoming review at each
chronological time step and represents the result using three categories:
likes, dislikes, and key features. The paper also states that structured JSON
schemas are used for reliable automatic post-processing, but it does not publish
the exact schema. This module therefore makes the project's schema choice
explicit while preserving the paper's three-part representation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping


SYSTEM_PROMPT = (
    "You are the Review Extractor component of a recommender system. "
    "Analyze the supplied purchased product and review as data. Extract only "
    "preferences that are supported by the review. Do not invent facts. "
    "Separate the result into likes, dislikes, and key product features that "
    "appear important to the user's preference or purchase decision."
)


@dataclass(frozen=True, slots=True)
class ReviewExtraction:
    """Structured representation extracted from one chronological interaction."""

    likes: tuple[str, ...]
    dislikes: tuple[str, ...]
    key_features: tuple[str, ...]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "likes": list(self.likes),
            "dislikes": list(self.dislikes),
            "key_features": list(self.key_features),
        }


def review_extractor_response_format() -> dict[str, object]:
    """Return the JSON-Schema response format used by the local runtime.

    The exact schema is a reproduction choice because the paper reports using
    JSON schemas but does not publish the machine-readable schema itself.
    Arrays may be empty when the review contains no supported evidence for a
    category. Entries must be non-empty strings and are not deduplicated here;
    redundancy resolution belongs to the later Profile Updater stage.
    """

    string_array = {
        "type": "array",
        "items": {"type": "string"},
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "pure_review_extraction",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "likes": string_array,
                    "dislikes": string_array,
                    "key_features": string_array,
                },
                "required": ["likes", "dislikes", "key_features"],
                "additionalProperties": False,
            },
        },
    }


def build_review_extractor_messages(
    interaction: Mapping[str, object],
) -> list[dict[str, str]]:
    """Build one incremental Review Extractor request.

    Algorithm 1 applies the extractor to the incoming review ``r_t``. We send
    one canonical interaction per call so the output can later be merged into
    the previous profile without re-extracting older reviews.

    ASIN, product name, and review text follow the paper's Step-1 prompt. The
    rating is also included because Figure 1 explicitly depicts PURE as using
    reviews, ratings, and item interactions. The paper does not clarify whether
    the rating is embedded inside the ``input reviews`` placeholder, so this is
    recorded as an explicit reproduction interpretation.
    """

    asin = str(interaction.get("asin", "")).strip()
    title = str(interaction.get("title", "")).strip()
    review_text = str(interaction.get("review_text", "")).strip()
    rating_value = interaction.get("rating")

    if not asin:
        raise ValueError("Review Extractor interaction is missing ASIN")
    if not title:
        raise ValueError("Review Extractor interaction is missing product title")
    if not review_text:
        raise ValueError("Review Extractor interaction is missing review text")
    if rating_value is None:
        raise ValueError("Review Extractor interaction is missing rating")

    try:
        rating = float(rating_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid Review Extractor rating: {rating_value!r}") from exc

    user_prompt = (
        "I purchased the following products and left reviews in chronological order:\n"
        "1.\n"
        f"ASIN: {asin}\n"
        f"Product name: {title}\n"
        f"Rating: {rating:g}\n"
        "Input review:\n"
        "<<<REVIEW>>>\n"
        f"{review_text}\n"
        "<<<END REVIEW>>>\n\n"
        "Analyze the user's likes/dislikes/key features by referring to their review.\n"
        "Use only evidence supported by the supplied review and product context.\n"
        "Keep each extracted entry concise and self-contained.\n"
        "Return only the structured response required by the JSON schema."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _extract_json_object(text: str) -> dict[str, object]:
    """Parse one JSON object, tolerating a surrounding Markdown code fence."""

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
        raise ValueError("Review Extractor response does not contain a JSON object")

    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Review Extractor response contains invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Review Extractor response must be a JSON object")
    return payload


def _parse_string_list(payload: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(payload, list):
        raise ValueError(f"Review Extractor field {field_name!r} must be an array")

    values: list[str] = []
    for value in payload:
        if not isinstance(value, str):
            raise ValueError(
                f"Review Extractor field {field_name!r} contains a non-string value: {value!r}"
            )
        normalized = value.strip()
        if not normalized:
            raise ValueError(
                f"Review Extractor field {field_name!r} contains an empty string"
            )
        values.append(normalized)
    return tuple(values)


def parse_review_extraction(text: str) -> ReviewExtraction:
    """Strictly validate and return one three-part extraction.

    No semantic repair, deduplication, inferred entries, or category migration is
    performed. The later Profile Updater is responsible for redundancy/conflict
    handling, matching the component separation described in PURE.
    """

    payload = _extract_json_object(text)
    expected_keys = {"likes", "dislikes", "key_features"}
    actual_keys = set(payload)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(actual_keys - expected_keys)
        raise ValueError(
            "Review Extractor response has incorrect keys; "
            f"missing={missing}, unexpected={unexpected}"
        )

    return ReviewExtraction(
        likes=_parse_string_list(payload["likes"], "likes"),
        dislikes=_parse_string_list(payload["dislikes"], "dislikes"),
        key_features=_parse_string_list(payload["key_features"], "key_features"),
    )
