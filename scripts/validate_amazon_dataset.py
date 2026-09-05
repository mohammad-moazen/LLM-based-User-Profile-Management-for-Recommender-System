"""Validate the local Amazon Video Games 5-core dataset for PURE reproduction.

This script performs a full streaming scan of both local ``.json.gz`` files.
It deliberately uses only the Python standard library, so it can be executed
before installing the project's later data-science dependencies.

The goal is not to modify the source dataset. Instead, we verify the exact
properties that matter for the PURE reproduction:

1. Required review fields are present.
2. Required metadata fields are present.
3. Review ASINs can be joined to product titles from metadata.
4. User interaction counts are suitable for sequential recommendation.
5. We understand duplicate user-item interactions and rating distribution.

Run from the repository root:

    python scripts/validate_amazon_dataset.py

By default the script expects these two files in the repository root:

    Video_Games_5.json.gz
    meta_Video_Games.json.gz

Alternative paths can be supplied with command-line arguments. For example:

    python scripts/validate_amazon_dataset.py \
        --reviews "D:/datasets/Video_Games_5.json.gz" \
        --metadata "D:/datasets/meta_Video_Games.json.gz"
"""

from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


REQUIRED_REVIEW_FIELDS = {
    "reviewerID",
    "asin",
    "reviewText",
    "overall",
    "unixReviewTime",
}

REQUIRED_METADATA_FIELDS = {
    "asin",
    "title",
}


def iter_json_gz(path: Path) -> Iterator[dict[str, Any]]:
    """Yield one JSON object at a time from a gzip-compressed JSON-lines file.

    Amazon Review Data 2018 category files are line-delimited JSON. Streaming
    them avoids loading the complete compressed dataset into memory at once.
    """

    with gzip.open(path, mode="rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in {path} at line {line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise TypeError(
                    f"Expected a JSON object in {path} at line {line_number}, "
                    f"but received {type(record).__name__}."
                )

            yield record


def percentile(sorted_values: list[int], fraction: float) -> float:
    """Return a simple nearest-rank-style percentile for integer values."""

    if not sorted_values:
        return 0.0

    index = round((len(sorted_values) - 1) * fraction)
    return float(sorted_values[index])


def validate_metadata(path: Path) -> tuple[dict[str, str], dict[str, int]]:
    """Scan metadata and build the ASIN -> title mapping needed by PURE."""

    asin_to_title: dict[str, str] = {}
    total_records = 0
    missing_required = 0
    duplicate_asins = 0
    empty_titles = 0

    for record in iter_json_gz(path):
        total_records += 1

        if not REQUIRED_METADATA_FIELDS.issubset(record):
            missing_required += 1
            continue

        asin = str(record.get("asin", "")).strip()
        title = str(record.get("title", "")).strip()

        if not asin:
            missing_required += 1
            continue

        if asin in asin_to_title:
            duplicate_asins += 1

        if not title:
            empty_titles += 1

        # Keep the first title for deterministic behavior when duplicate ASINs
        # appear in metadata. Later preprocessing can apply a different policy
        # if the validation report shows that duplicates are meaningful.
        asin_to_title.setdefault(asin, title)

    stats = {
        "total_records": total_records,
        "missing_required": missing_required,
        "duplicate_asins": duplicate_asins,
        "empty_titles": empty_titles,
        "unique_asins": len(asin_to_title),
    }
    return asin_to_title, stats


def validate_reviews(
    path: Path,
    asin_to_title: dict[str, str],
) -> dict[str, Any]:
    """Scan the full review file and collect PURE-relevant statistics."""

    total_reviews = 0
    missing_required = 0
    empty_review_text = 0
    metadata_misses = 0

    user_counts: Counter[str] = Counter()
    item_counts: Counter[str] = Counter()
    rating_counts: Counter[float] = Counter()

    # Tracking user-item pairs lets us determine whether the source file
    # contains repeated interactions for the same user and product. We do not
    # remove any records here; this is strictly a validation step.
    seen_user_item: set[tuple[str, str]] = set()
    repeated_user_item_rows = 0

    for record in iter_json_gz(path):
        total_reviews += 1

        if not REQUIRED_REVIEW_FIELDS.issubset(record):
            missing_required += 1
            continue

        user_id = str(record.get("reviewerID", "")).strip()
        asin = str(record.get("asin", "")).strip()
        review_text = record.get("reviewText")
        rating = record.get("overall")

        if not user_id or not asin:
            missing_required += 1
            continue

        if not isinstance(review_text, str) or not review_text.strip():
            empty_review_text += 1

        if asin not in asin_to_title or not asin_to_title.get(asin, "").strip():
            metadata_misses += 1

        user_counts[user_id] += 1
        item_counts[asin] += 1

        try:
            rating_counts[float(rating)] += 1
        except (TypeError, ValueError):
            # A malformed rating is already useful information for validation.
            rating_counts[float("nan")] += 1

        pair = (user_id, asin)
        if pair in seen_user_item:
            repeated_user_item_rows += 1
        else:
            seen_user_item.add(pair)

    history_lengths = sorted(user_counts.values())

    users_ge_3 = sum(count >= 3 for count in history_lengths)
    users_ge_4 = sum(count >= 4 for count in history_lengths)
    users_ge_5 = sum(count >= 5 for count in history_lengths)

    return {
        "total_reviews": total_reviews,
        "missing_required": missing_required,
        "empty_review_text": empty_review_text,
        "metadata_misses": metadata_misses,
        "metadata_coverage_pct": (
            100.0 * (total_reviews - metadata_misses) / total_reviews
            if total_reviews
            else 0.0
        ),
        "unique_users": len(user_counts),
        "unique_items_in_reviews": len(item_counts),
        "repeated_user_item_rows": repeated_user_item_rows,
        "users_ge_3": users_ge_3,
        "users_ge_4": users_ge_4,
        "users_ge_5": users_ge_5,
        "history_min": min(history_lengths) if history_lengths else 0,
        "history_median": statistics.median(history_lengths)
        if history_lengths
        else 0,
        "history_mean": statistics.mean(history_lengths)
        if history_lengths
        else 0,
        "history_p90": percentile(history_lengths, 0.90),
        "history_p95": percentile(history_lengths, 0.95),
        "history_max": max(history_lengths) if history_lengths else 0,
        "rating_counts": dict(sorted(rating_counts.items(), key=lambda item: item[0])),
    }


def print_report(
    review_path: Path,
    metadata_path: Path,
    metadata_stats: dict[str, int],
    review_stats: dict[str, Any],
) -> None:
    """Print a compact report that can be copied back into the project chat."""

    separator = "=" * 88
    print(separator)
    print("PURE DATASET VALIDATION REPORT")
    print(separator)
    print(f"Reviews file : {review_path}")
    print(f"Metadata file: {metadata_path}")

    print("\n[Metadata]")
    for key, value in metadata_stats.items():
        print(f"  {key:28s}: {value}")

    print("\n[Reviews / interactions]")
    ordered_keys = [
        "total_reviews",
        "unique_users",
        "unique_items_in_reviews",
        "missing_required",
        "empty_review_text",
        "metadata_misses",
        "metadata_coverage_pct",
        "repeated_user_item_rows",
    ]
    for key in ordered_keys:
        value = review_stats[key]
        if key.endswith("_pct"):
            print(f"  {key:28s}: {value:.4f}%")
        else:
            print(f"  {key:28s}: {value}")

    print("\n[User history lengths]")
    for key in [
        "users_ge_3",
        "users_ge_4",
        "users_ge_5",
        "history_min",
        "history_median",
        "history_mean",
        "history_p90",
        "history_p95",
        "history_max",
    ]:
        value = review_stats[key]
        if isinstance(value, float):
            print(f"  {key:28s}: {value:.2f}")
        else:
            print(f"  {key:28s}: {value}")

    print("\n[Rating distribution]")
    for rating, count in review_stats["rating_counts"].items():
        print(f"  rating={rating:<4}: {count}")

    print("\n[Initial PURE suitability checks]")
    checks = {
        "No required-field failures": review_stats["missing_required"] == 0,
        "All metadata rows have required fields": metadata_stats["missing_required"] == 0,
        "Review-to-title coverage >= 99%": review_stats["metadata_coverage_pct"] >= 99.0,
        "Users available for >=3-history prediction": review_stats["users_ge_3"] > 0,
    }

    for label, passed in checks.items():
        print(f"  {'PASS' if passed else 'CHECK':5s} - {label}")

    print(separator)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Validate Amazon Video Games 5-core data for PURE reproduction."
    )
    parser.add_argument(
        "--reviews",
        type=Path,
        default=Path("Video_Games_5.json.gz"),
        help="Path to Video_Games_5.json.gz",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("meta_Video_Games.json.gz"),
        help="Path to meta_Video_Games.json.gz",
    )
    return parser.parse_args()


def main() -> int:
    """Validate both files and print the resulting report."""

    args = parse_args()
    review_path = args.reviews.resolve()
    metadata_path = args.metadata.resolve()

    for path in (review_path, metadata_path):
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            return 1

    print("Scanning metadata...", flush=True)
    asin_to_title, metadata_stats = validate_metadata(metadata_path)

    print("Scanning reviews...", flush=True)
    review_stats = validate_reviews(review_path, asin_to_title)

    print_report(
        review_path=review_path,
        metadata_path=metadata_path,
        metadata_stats=metadata_stats,
        review_stats=review_stats,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
