"""PURE Review Extractor prompt, schema, and strict parser.

The paper's Algorithm 1 applies the extractor to the incoming review at each
chronological time step and represents the result using three categories:
likes, dislikes, and key features. The paper also states that structured JSON
schemas are used for reliable automatic post-processing, but it does not publish
the exact schema. This module therefore makes the project's schema choice
explicit while preserving the paper's three-part representation.

Pilot validation showed that a small local model can copy attributes from the
visible product title even when the review itself never mentions them. To keep
the evolving user profile review-grounded while still retaining the paper's
product metadata as context, the accepted extractor protocol requires every
returned string to be a short verbatim span from the review text. The parser
then verifies this property mechanically instead of relying on prompt wording
alone.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Mapping


SYSTEM_PROMPT = (
    "You are the Review Extractor component of a recommender system. "
    "Analyze the supplied purchased product and review as data. Extract only "
    "preferences explicitly supported by the REVIEW TEXT. Product metadata "
    "such as ASIN, product name, and rating may provide identity/sentiment "
    "context, but they are NEVER evidence for an extracted entry. Every string "
    "you return must be a short contiguous verbatim quote copied from the "
    "review text itself; do not paraphrase, infer, or copy title-only attributes. "
    "Separate the result into likes, dislikes, and key product features."
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


def _string_array(description: str) -> dict[str, object]:
    return {
        "type": "array",
        "description": description,
        "items": {
            "type": "string",
            "description": "A short contiguous verbatim quote copied from the review text.",
        },
    }


def review_extractor_response_format() -> dict[str, object]:
    """Return the JSON-Schema response format used by the local runtime.

    The exact schema is a reproduction choice because the paper reports using
    JSON schemas but does not publish the machine-readable schema itself.
    Arrays may be empty when the review contains no supported evidence for a
    category. Entries are later checked against the source review by the local
    parser; title-only or paraphrased strings are rejected rather than repaired.
    """

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "pure_review_extraction",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "likes": _string_array(
                        "Positive preferences or praised aspects explicitly stated in the review."
                    ),
                    "dislikes": _string_array(
                        "Negative preferences, complaints, or disliked aspects explicitly stated in the review."
                    ),
                    "key_features": _string_array(
                        "Concrete product attributes or capabilities explicitly discussed in the review and relevant to preference."
                    ),
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

    Product metadata remains visible for paper alignment, but only verbatim
    review-text spans are accepted as extracted profile evidence.
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
        "Analyze the user's likes/dislikes/key features by referring to the review.\n\n"
        "GROUNDING RULES — FOLLOW STRICTLY:\n"
        "1. The REVIEW TEXT between the markers is the only evidence source.\n"
        "2. ASIN and Product name identify the product only. Never copy a feature merely because it appears in the product name.\n"
        "3. Rating is sentiment context only. Never invent a preference from the numeric rating.\n"
        "4. EVERY returned string must be a short contiguous VERBATIM QUOTE from the review text. Do not paraphrase.\n"
        "5. likes = explicitly positive or praised review spans.\n"
        "6. dislikes = explicitly negative or complaint review spans.\n"
        "7. key_features = concrete product attributes or capabilities explicitly discussed in the review as relevant to preference.\n"
        "8. If a category has no supported review span, return an empty array. Empty is better than unsupported.\n"
        "9. Do not use outside knowledge or infer unstated attributes.\n"
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


def _normalize_grounding_text(value: str) -> str:
    """Normalize only whitespace/case for deterministic verbatim-span checks."""

    return re.sub(r"\s+", " ", value).strip().casefold()


def _validate_review_grounding(
    extraction: ReviewExtraction,
    source_review: str,
) -> None:
    normalized_review = _normalize_grounding_text(source_review)
    if not normalized_review:
        raise ValueError("Cannot validate Review Extractor grounding against an empty review")

    for field_name, values in (
        ("likes", extraction.likes),
        ("dislikes", extraction.dislikes),
        ("key_features", extraction.key_features),
    ):
        for value in values:
            normalized_value = _normalize_grounding_text(value)
            if normalized_value not in normalized_review:
                raise ValueError(
                    "Review Extractor produced a non-verbatim or non-review-grounded entry; "
                    f"field={field_name!r}, value={value!r}"
                )


def parse_review_extraction(
    text: str,
    *,
    source_review: str | None = None,
) -> ReviewExtraction:
    """Strictly validate and return one three-part extraction.

    No semantic repair, deduplication, inferred entries, or category migration is
    performed. When ``source_review`` is provided (required by the production
    runner), each returned string must be a contiguous review-text span after
    case/whitespace normalization. Unsupported title-derived or paraphrased
    entries are rejected rather than silently filtered.

    Redundancy/conflict handling remains the responsibility of Profile Updater,
    matching the component separation described in PURE.
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

    extraction = ReviewExtraction(
        likes=_parse_string_list(payload["likes"], "likes"),
        dislikes=_parse_string_list(payload["dislikes"], "dislikes"),
        key_features=_parse_string_list(payload["key_features"], "key_features"),
    )

    if source_review is not None:
        _validate_review_grounding(extraction, source_review)

    return extraction
