"""Small immutable data models used by the Phase 1 pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalInteraction:
    user_id: str
    asin: str
    title: str
    review_text: str
    rating: float
    timestamp: int
    source_row_index: int

    def to_public_dict(self) -> dict[str, object]:
        """Return the canonical experiment schema without the tie-break helper."""
        return {
            "user_id": self.user_id,
            "asin": self.asin,
            "title": self.title,
            "review_text": self.review_text,
            "rating": self.rating,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class RecommendationSession:
    session_id: str
    user_id: str
    target_position: int
    target_asin: str
    candidate_asins: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "target_position": self.target_position,
            "target_asin": self.target_asin,
            "candidate_asins": list(self.candidate_asins),
        }
