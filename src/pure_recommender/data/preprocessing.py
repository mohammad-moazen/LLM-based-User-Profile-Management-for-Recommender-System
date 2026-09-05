"""Canonical preprocessing for Amazon Video Games according to policy v1.

The paper does not document these cleaning edge cases. The exact rules are
therefore defined in ``docs/PREPROCESSING_POLICY.md`` and implemented here.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import gzip
import json
from pathlib import Path
from statistics import mean, median
from typing import Iterable, Iterator

from .models import CanonicalInteraction


_REQUIRED_REVIEW_FIELDS = (
    "reviewerID",
    "asin",
    "reviewText",
    "overall",
    "unixReviewTime",
)


@dataclass(slots=True)
class PreprocessingReport:
    metadata_rows: int = 0
    metadata_unique_asins: int = 0
    metadata_duplicate_asin_groups: int = 0
    metadata_empty_titles: int = 0
    raw_review_rows: int = 0
    dropped_missing_required: int = 0
    dropped_missing_metadata_title: int = 0
    dropped_missing_metadata_unique_asins: int = 0
    exact_duplicate_groups_collapsed: int = 0
    exact_duplicate_rows_removed: int = 0
    ambiguous_pair_groups_excluded: int = 0
    ambiguous_pair_rows_excluded: int = 0
    final_interactions: int = 0
    final_users: int = 0
    final_items: int = 0
    eligible_users: int = 0
    history_min: int = 0
    history_median: float = 0.0
    history_mean: float = 0.0
    history_max: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _iter_gzip_json_lines(path: Path) -> Iterator[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object in {path} at line {line_number}")
            yield value


def load_metadata_titles(path: Path, report: PreprocessingReport) -> dict[str, str]:
    """Create one deterministic usable title per ASIN."""
    occurrences: Counter[str] = Counter()
    titles: dict[str, str] = {}

    for row in _iter_gzip_json_lines(path):
        report.metadata_rows += 1
        asin = str(row.get("asin", "")).strip()
        title = str(row.get("title", "")).strip()
        if not asin:
            continue

        occurrences[asin] += 1
        if not title:
            report.metadata_empty_titles += 1
            continue

        existing = titles.get(asin)
        if existing is None:
            titles[asin] = title
        elif existing != title:
            raise ValueError(
                f"Conflicting non-empty metadata titles found for ASIN {asin!r}: "
                f"{existing!r} vs {title!r}"
            )

    report.metadata_unique_asins = len(occurrences)
    report.metadata_duplicate_asin_groups = sum(1 for count in occurrences.values() if count > 1)
    return titles


def _parse_review_row(
    row: dict[str, object],
    source_row_index: int,
    metadata_titles: dict[str, str],
) -> tuple[CanonicalInteraction | None, str | None]:
    """Parse one row and return an interaction or a deterministic drop reason."""
    for field in _REQUIRED_REVIEW_FIELDS:
        if field not in row or row[field] is None:
            return None, "missing_required"

    user_id = str(row["reviewerID"]).strip()
    asin = str(row["asin"]).strip()
    review_text = str(row["reviewText"]).strip()
    if not user_id or not asin or not review_text:
        return None, "missing_required"

    try:
        rating = float(row["overall"])
        timestamp = int(row["unixReviewTime"])
    except (TypeError, ValueError):
        return None, "missing_required"

    title = metadata_titles.get(asin)
    if not title:
        return None, "missing_metadata_title"

    return (
        CanonicalInteraction(
            user_id=user_id,
            asin=asin,
            title=title,
            review_text=review_text,
            rating=rating,
            timestamp=timestamp,
            source_row_index=source_row_index,
        ),
        None,
    )


def preprocess_reviews(
    reviews_path: Path,
    metadata_titles: dict[str, str],
    report: PreprocessingReport,
) -> list[CanonicalInteraction]:
    """Apply required-field, metadata-join, and repeated-pair policy v1."""
    grouped: dict[tuple[str, str], list[CanonicalInteraction]] = defaultdict(list)
    missing_title_asins: set[str] = set()

    for source_row_index, row in enumerate(_iter_gzip_json_lines(reviews_path)):
        report.raw_review_rows += 1
        interaction, reason = _parse_review_row(row, source_row_index, metadata_titles)
        if reason == "missing_required":
            report.dropped_missing_required += 1
            continue
        if reason == "missing_metadata_title":
            report.dropped_missing_metadata_title += 1
            asin = str(row.get("asin", "")).strip()
            if asin:
                missing_title_asins.add(asin)
            continue
        assert interaction is not None
        grouped[(interaction.user_id, interaction.asin)].append(interaction)

    report.dropped_missing_metadata_unique_asins = len(missing_title_asins)

    canonical: list[CanonicalInteraction] = []
    for rows in grouped.values():
        if len(rows) == 1:
            canonical.append(rows[0])
            continue

        signatures = {(row.timestamp, row.rating, row.review_text) for row in rows}
        if len(signatures) == 1:
            report.exact_duplicate_groups_collapsed += 1
            report.exact_duplicate_rows_removed += len(rows) - 1
            canonical.append(min(rows, key=lambda row: row.source_row_index))
        else:
            report.ambiguous_pair_groups_excluded += 1
            report.ambiguous_pair_rows_excluded += len(rows)

    canonical.sort(key=lambda row: (row.user_id, row.timestamp, row.source_row_index, row.asin))
    return canonical


def summarize_histories(
    interactions: Iterable[CanonicalInteraction],
    report: PreprocessingReport,
    min_history: int,
) -> None:
    interactions = list(interactions)
    counts: Counter[str] = Counter(row.user_id for row in interactions)
    history_lengths = list(counts.values())

    report.final_interactions = len(interactions)
    report.final_users = len(counts)
    report.final_items = len({row.asin for row in interactions})
    report.eligible_users = sum(length >= min_history + 1 for length in history_lengths)

    if history_lengths:
        report.history_min = min(history_lengths)
        report.history_median = float(median(history_lengths))
        report.history_mean = float(mean(history_lengths))
        report.history_max = max(history_lengths)


def build_canonical_dataset(
    reviews_path: Path,
    metadata_path: Path,
    min_history: int,
) -> tuple[list[CanonicalInteraction], dict[str, str], PreprocessingReport]:
    """Build the canonical interaction list and candidate item map."""
    report = PreprocessingReport()
    metadata_titles = load_metadata_titles(metadata_path, report)
    interactions = preprocess_reviews(reviews_path, metadata_titles, report)
    summarize_histories(interactions, report, min_history=min_history)

    # Candidate items are restricted to products that survive into the cleaned
    # interaction dataset, not metadata-only products with no canonical event.
    canonical_items = {row.asin: row.title for row in interactions}
    return interactions, canonical_items, report
