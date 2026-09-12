"""PURE Review Extractor prompt, schema, and conservative evidence validation.

The paper's Algorithm 1 extracts likes, dislikes, and key features from the
incoming review and reports using JSON-schema structured outputs, but it does
not publish the exact schema or grounding/post-processing rules.

Pilot v1/v2 showed title leakage. Pilot v3 made every output string verbatim and
became too restrictive for legitimate paraphrases. Pilot v4 separated a concise
``value`` from a verbatim ``evidence`` span, but the local derivative model could
still occasionally fabricate an evidence span from the visible product title.

The accepted policy therefore validates each generated entry independently:
- ``value`` may be a concise paraphrase/normalization;
- ``evidence`` should be a non-empty contiguous span of the review text;
- entries with empty or unsupported evidence are rejected and logged individually;
- valid entries from the same response are preserved;
- downstream profile input uses only validated review evidence spans.

This is conservative filtering, not semantic repair: rejected entries are not
rewritten, inferred, or replaced.
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
    "evidence quote copied from the review text itself. Never return an empty "
    "evidence string; omit the entry instead. Do not invent facts or use title-only "
    "attributes."
)


@dataclass(frozen=True, slots=True)
class ReviewEvidenceEntry:
    """One model interpretation anchored to a claimed review-text span."""

    value: str
    evidence: str


@dataclass(frozen=True, slots=True)
class RejectedEvidenceEntry:
    """One generated entry rejected by deterministic grounding validation."""

    field: str
    value: str
    evidence: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "value": self.value,
            "evidence": self.evidence,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ReviewExtraction:
    """Validated evidence-backed representation extracted from one interaction."""

    likes: tuple[ReviewEvidenceEntry, ...]
    dislikes: tuple[ReviewEvidenceEntry, ...]
    key_features: tuple[ReviewEvidenceEntry, ...]
    rejected_entries: tuple[RejectedEvidenceEntry, ...] = ()

    def to_profile_dict(self) -> dict[str, list[str]]:
        """Return only validated review-verbatim evidence safe for profile input."""

        return {
            "likes": [entry.evidence for entry in self.likes],
            "dislikes": [entry.evidence for entry in self.dislikes],
            "key_features": [entry.evidence for entry in self.key_features],
        }

    def to_audit_dict(self) -> dict[str, list[dict[str, str]]]:
        """Return accepted model values plus validated evidence for audit."""

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

    def rejected_to_dict(self) -> list[dict[str, str]]:
        return [entry.to_dict() for entry in self.rejected_entries]

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
                    "minLength": 1,
                    "description": "Concise interpretation of the preference/feature.",
                },
                "evidence": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Short contiguous verbatim quote copied exactly from the review text.",
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
        "5. Never return an empty evidence string. If there is no exact review evidence, omit that entry entirely.\n"
        "6. The value must faithfully summarize only what its evidence supports; do not add an unstated attribute.\n"
        "7. likes = positive/praised aspects; dislikes = negative/complaint aspects; key_features = concrete attributes/capabilities relevant to preference.\n"
        "8. If a category has no supported evidence, return an empty array. Empty is better than unsupported.\n"
        "9. Do not use outside knowledge.\n"
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
        if not isinstance(evidence, str):
            raise ValueError(f"Review Extractor field {field_name!r} contains non-string evidence")
        # Blank evidence is a semantic grounding failure, not a structural failure.
        # Keep it here so the entry-level partitioner can reject/log only this item.
        entries.append(ReviewEvidenceEntry(value=value.strip(), evidence=evidence.strip()))
    return tuple(entries)


def _normalize_grounding_text(value: str) -> str:
    """Normalize case/whitespace only for deterministic evidence-span checks."""

    return re.sub(r"\s+", " ", value).strip().casefold()


def _partition_grounded_entries(
    extraction: ReviewExtraction,
    source_review: str,
) -> ReviewExtraction:
    normalized_review = _normalize_grounding_text(source_review)
    if not normalized_review:
        raise ValueError("Cannot validate Review Extractor grounding against an empty review")

    accepted: dict[str, list[ReviewEvidenceEntry]] = {
        "likes": [],
        "dislikes": [],
        "key_features": [],
    }
    rejected: list[RejectedEvidenceEntry] = []

    for field_name, entries in (
        ("likes", extraction.likes),
        ("dislikes", extraction.dislikes),
        ("key_features", extraction.key_features),
    ):
        for entry in entries:
            normalized_evidence = _normalize_grounding_text(entry.evidence)
            if not normalized_evidence:
                rejected.append(
                    RejectedEvidenceEntry(
                        field=field_name,
                        value=entry.value,
                        evidence=entry.evidence,
                        reason="empty_evidence",
                    )
                )
            elif normalized_evidence in normalized_review:
                accepted[field_name].append(entry)
            else:
                rejected.append(
                    RejectedEvidenceEntry(
                        field=field_name,
                        value=entry.value,
                        evidence=entry.evidence,
                        reason="evidence_not_contiguous_span_of_review",
                    )
                )

    return ReviewExtraction(
        likes=tuple(accepted["likes"]),
        dislikes=tuple(accepted["dislikes"]),
        key_features=tuple(accepted["key_features"]),
        rejected_entries=tuple(rejected),
    )


def parse_review_extraction(
    text: str,
    *,
    source_review: str | None = None,
) -> ReviewExtraction:
    """Parse one evidence-backed extraction and conservatively reject bad entries.

    Structural schema violations still fail the whole response. When a source
    review is provided, grounding is evaluated entry-by-entry: blank evidence or
    evidence that is not a contiguous review span is excluded from the profile-safe
    representation and kept in ``rejected_entries`` for audit. No rejected entry
    is rewritten or replaced.
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
        extraction = _partition_grounded_entries(extraction, source_review)
    return extraction
