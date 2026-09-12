"""PURE Review Extractor prompt, schema, and strict evidence validation.

The paper's Algorithm 1 extracts likes, dislikes, and key features from the
incoming review. The paper also reports JSON-schema structured outputs but does
not publish the exact schema.

Pilot v1/v2 showed that a small local model may copy title-only attributes. A
strict verbatim-only output rule in pilot v3 fixed title leakage but rejected a
legitimate paraphrase (``breathing LEDs``) even though the review explicitly said
that the LEDs can ``breathe``. The accepted protocol therefore separates the
model's concise interpretation from its evidence span:

- ``value`` may be a concise paraphrase/normalization;
- ``evidence`` must be a short contiguous verbatim span from the review text;
- only evidence-backed entries are accepted;
- the downstream safe extraction uses the verbatim evidence spans, while the
  model's normalized values are retained only for audit/inspection.

This preserves semantic flexibility without allowing product-title-only content
to enter the evolving profile.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Mapping


SYSTEM_PROMPT = (
    "You are the Review Extractor component of a recommender system. "
    "Extract user likes, dislikes, and key product features from the REVIEW TEXT. "
    "Product metadata such as ASIN, product name, and rating may provide identity "
    "or sentiment context, but they are never independent evidence. For every "
    "extracted entry return both a concise value and a short contiguous verbatim "
    "evidence quote copied from the review text itself. Do not invent facts or use "
    "title-only attributes."
)


@dataclass(frozen=True, slots=True)
class ReviewEvidenceEntry:
    """One model interpretation anchored to an exact review-text span."""

    value: str
    evidence: str


@dataclass(frozen=True, slots=True)
class ReviewExtraction:
    """Evidence-backed representation extracted from one interaction."""

    likes: tuple[ReviewEvidenceEntry, ...]
    dislikes: tuple[ReviewEvidenceEntry, ...]
    key_features: tuple[ReviewEvidenceEntry, ...]

    def to_profile_dict(self) -> dict[str, list[str]]:
        """Return only review-verbatim evidence strings safe for profile input."""

        return {
            "likes": [entry.evidence for entry in self.likes],
            "dislikes": [entry.evidence for entry in self.dislikes],
            "key_features": [entry.evidence for entry in self.key_features],
        }

    def to_audit_dict(self) -> dict[str, list[dict[str, str]]]:
        """Return model values plus evidence for debugging and qualitative audit."""

        return {
            "likes": [
                {"value": entry.value, "evidence": entry.evidence}
                for entry in self.likes
            ],
            "dislikes": [
                {"value": entry.value, "evidence": entry.evidence}
                for entry in self.dislikes
            ],
            "key_features": [
                {"value": entry.value, "evidence": entry.evidence}
                for entry in self.key_features
            ],
        }

    # Backward-friendly name used by runner/tests: downstream-safe profile data.
    def to_dict(self) -> dict[str, list[str]]:
        return self.to_profile_dict()


def _entry_array(description: str) -> dict[str, object]:
    return {
        "type": "array",
        "description": description,
        "items": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "description": "Concise interpretation of the preference/feature.",
                },
                "evidence": {
                    "type": "string",
                    "description": (
                        "Short contiguous verbatim quote copied exactly from the review text."
                    ),
                },
            },
            "required": ["value", "evidence"],
            "additionalProperties": False,
        },
    }


def review_extractor_response_format() -> dict[str, object]:
    """Return the project-defined evidence-backed JSON schema."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "pure_review_extraction_evidence_backed",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "likes": _entry_array(
                        "Positive preferences or praised aspects supported by the review."
                    ),
                    "dislikes": _entry_array(
                        "Negative preferences or complaints supported by the review."
                    ),
                    "key_features": _entry_array(
                        "Concrete product attributes/capabilities discussed in the review."
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
    """Build one incremental Review Extractor request."""

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
        "2. ASIN and Product name identify the product only; never use a title-only attribute as evidence.\n"
        "3. Rating is sentiment context only; never invent a specific preference from the numeric rating.\n"
        "4. For every entry, value may be a concise paraphrase, but evidence MUST be a short contiguous VERBATIM quote from the review text.\n"
        "5. The value must faithfully summarize only what its evidence supports; do not add an unstated attribute.\n"
        "6. likes = positive/praised aspects; dislikes = negative/complaint aspects; key_features = concrete attributes/capabilities relevant to preference.\n"
        "7. If a category has no supported evidence, return an empty array. Empty is better than unsupported.\n"
        "8. Do not use outside knowledge.\n"
        "Return only the structured response required by the JSON schema."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _extract_json_object(text: str) -> dict[str, object]:
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


def _parse_entry_list(payload: object, field_name: str) -> tuple[ReviewEvidenceEntry, ...]:
    if not isinstance(payload, list):
        raise ValueError(f"Review Extractor field {field_name!r} must be an array")

    entries: list[ReviewEvidenceEntry] = []
    for item in payload:
        if not isinstance(item, dict) or set(item) != {"value", "evidence"}:
            raise ValueError(
                f"Review Extractor field {field_name!r} must contain only value/evidence objects"
            )
        value = item.get("value")
        evidence = item.get("evidence")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Review Extractor field {field_name!r} contains invalid value")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(f"Review Extractor field {field_name!r} contains invalid evidence")
        entries.append(ReviewEvidenceEntry(value=value.strip(), evidence=evidence.strip()))
    return tuple(entries)


def _normalize_grounding_text(value: str) -> str:
    """Normalize case/whitespace only for deterministic evidence-span checks."""

    return re.sub(r"\s+", " ", value).strip().casefold()


def _validate_review_grounding(
    extraction: ReviewExtraction,
    source_review: str,
) -> None:
    normalized_review = _normalize_grounding_text(source_review)
    if not normalized_review:
        raise ValueError("Cannot validate Review Extractor grounding against an empty review")

    for field_name, entries in (
        ("likes", extraction.likes),
        ("dislikes", extraction.dislikes),
        ("key_features", extraction.key_features),
    ):
        for entry in entries:
            normalized_evidence = _normalize_grounding_text(entry.evidence)
            if normalized_evidence not in normalized_review:
                raise ValueError(
                    "Review Extractor produced non-verbatim review evidence; "
                    f"field={field_name!r}, value={entry.value!r}, evidence={entry.evidence!r}"
                )


def parse_review_extraction(
    text: str,
    *,
    source_review: str | None = None,
) -> ReviewExtraction:
    """Parse and strictly validate one evidence-backed extraction.

    No semantic repair, deduplication, category migration, or inferred evidence is
    performed. When a source review is provided, every evidence string must be a
    contiguous review span after case/whitespace normalization.
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
        likes=_parse_entry_list(payload["likes"], "likes"),
        dislikes=_parse_entry_list(payload["dislikes"], "dislikes"),
        key_features=_parse_entry_list(payload["key_features"], "key_features"),
    )
    if source_review is not None:
        _validate_review_grounding(extraction, source_review)
    return extraction
