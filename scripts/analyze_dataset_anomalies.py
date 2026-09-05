"""Inspect important Amazon Video Games dataset anomalies before preprocessing.

This script is intentionally diagnostic rather than corrective.  Its job is to
show us *what the questionable rows actually look like* before we freeze any
cleaning rule for the PURE reproduction pipeline.

Why this matters
----------------
The full validation run found four categories that need inspection:

1. Duplicate ASIN records in the metadata file.
2. Repeated (reviewerID, asin) pairs in the review file.
3. Review rows missing at least one required PURE field.
4. Review ASINs that cannot be joined to the metadata title lookup.

For a scientific reproduction, we should not silently deduplicate or drop data
until we understand these cases.  This script therefore reports counts and
prints representative examples only.  It does not modify either source file.

The two expected input files are searched for in the repository root by
default:

- Video_Games_5.json.gz
- meta_Video_Games.json.gz

They can also be supplied explicitly through command-line arguments.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REVIEW_REQUIRED_FIELDS = (
    "reviewerID",
    "asin",
    "reviewText",
    "overall",
    "unixReviewTime",
)

METADATA_REQUIRED_FIELDS = ("asin", "title")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def iter_json_gz(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield one decoded JSON object per line from a gzip-compressed JSONL file.

    Amazon Review Data 2018 uses one JSON object per line.  Streaming the file
    keeps memory usage modest and lets this script run comfortably on a laptop.
    """

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in {path} at line {line_number}: {exc}"
                ) from exc


def compact_json(value: Any, max_chars: int = 700) -> str:
    """Return a readable compact JSON representation for terminal diagnostics."""

    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def print_heading(title: str) -> None:
    """Print a consistent section heading."""

    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def print_subheading(title: str) -> None:
    """Print a smaller section heading."""

    print("\n" + "-" * 100)
    print(title)
    print("-" * 100)


# ---------------------------------------------------------------------------
# Metadata analysis
# ---------------------------------------------------------------------------

def analyze_metadata(
    metadata_path: Path,
    sample_limit: int,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
    """Inspect duplicate ASIN metadata records and construct a title lookup.

    Returns
    -------
    duplicate_examples:
        A limited collection of duplicate-ASIN record groups for display.
    title_lookup:
        A deterministic first-non-empty-title lookup used only by the later
        metadata-miss diagnostic.  This does *not* yet define our final cleaning
        policy.
    """

    asin_counts: Counter[str] = Counter()
    first_records: Dict[str, Dict[str, Any]] = {}
    duplicate_examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    title_lookup: Dict[str, str] = {}

    total_records = 0
    empty_asin_rows = 0
    empty_title_rows = 0

    for record in iter_json_gz(metadata_path):
        total_records += 1

        asin = record.get("asin")
        title = record.get("title")

        if not isinstance(asin, str) or not asin.strip():
            empty_asin_rows += 1
            continue

        asin = asin.strip()
        asin_counts[asin] += 1

        if not isinstance(title, str) or not title.strip():
            empty_title_rows += 1
        elif asin not in title_lookup:
            # This lookup is used only to detect review ASINs with no usable
            # metadata title.  We intentionally do not claim yet that "first
            # non-empty title wins" is our final preprocessing policy.
            title_lookup[asin] = title.strip()

        if asin not in first_records:
            first_records[asin] = record
        elif len(duplicate_examples) < sample_limit or asin in duplicate_examples:
            # Keep the original record together with duplicate occurrences so
            # that we can compare fields such as title, category, brand, etc.
            if asin not in duplicate_examples:
                duplicate_examples[asin].append(first_records[asin])
            duplicate_examples[asin].append(record)

    duplicate_asins = [asin for asin, count in asin_counts.items() if count > 1]

    # Measure whether duplicate ASINs actually disagree on title.  We need a
    # second streaming pass because retaining all duplicate records in memory is
    # unnecessary for this diagnostic.
    duplicate_asin_set = set(duplicate_asins)
    duplicate_titles: Dict[str, set[str]] = defaultdict(set)

    for record in iter_json_gz(metadata_path):
        asin = record.get("asin")
        if not isinstance(asin, str):
            continue
        asin = asin.strip()
        if asin not in duplicate_asin_set:
            continue

        title = record.get("title")
        if isinstance(title, str) and title.strip():
            duplicate_titles[asin].add(title.strip())

    duplicate_asins_with_conflicting_titles = sum(
        1 for titles in duplicate_titles.values() if len(titles) > 1
    )

    print_heading("1. METADATA DUPLICATE-ASIN ANALYSIS")
    print(f"Total metadata records                   : {total_records}")
    print(f"Unique ASINs                             : {len(asin_counts)}")
    print(f"ASINs occurring more than once           : {len(duplicate_asins)}")
    print(f"Rows with empty/invalid ASIN             : {empty_asin_rows}")
    print(f"Rows with empty/invalid title            : {empty_title_rows}")
    print(
        "Duplicate ASINs with >1 non-empty title   : "
        f"{duplicate_asins_with_conflicting_titles}"
    )

    print_subheading(f"Representative duplicate metadata groups (up to {sample_limit})")
    if not duplicate_examples:
        print("No duplicate metadata examples found.")
    else:
        for index, (asin, records) in enumerate(duplicate_examples.items(), start=1):
            print(f"\nExample {index} — ASIN={asin}, shown_records={len(records)}")
            for record_index, record in enumerate(records, start=1):
                interesting = {
                    "asin": record.get("asin"),
                    "title": record.get("title"),
                    "brand": record.get("brand"),
                    "main_cat": record.get("main_cat"),
                    "category": record.get("category"),
                }
                print(f"  Record {record_index}: {compact_json(interesting)}")

    return duplicate_examples, title_lookup


# ---------------------------------------------------------------------------
# Review analysis
# ---------------------------------------------------------------------------

def analyze_reviews(
    reviews_path: Path,
    title_lookup: Dict[str, str],
    sample_limit: int,
) -> None:
    """Inspect missing fields, metadata misses, and repeated user-item pairs."""

    pair_counts: Counter[Tuple[str, str]] = Counter()
    first_pair_record: Dict[Tuple[str, str], Dict[str, Any]] = {}
    repeated_pair_examples: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)

    missing_required_count = 0
    missing_required_examples: List[Dict[str, Any]] = []

    metadata_miss_count = 0
    metadata_miss_asins: Counter[str] = Counter()
    metadata_miss_examples: List[Dict[str, Any]] = []

    total_records = 0

    for record in iter_json_gz(reviews_path):
        total_records += 1

        missing_fields = [
            field
            for field in REVIEW_REQUIRED_FIELDS
            if field not in record or record.get(field) is None
        ]

        if missing_fields:
            missing_required_count += 1
            if len(missing_required_examples) < sample_limit:
                missing_required_examples.append(
                    {
                        "missing_fields": missing_fields,
                        "record": record,
                    }
                )

        reviewer_id = record.get("reviewerID")
        asin = record.get("asin")

        # Only form a user-item pair when both identifiers are valid strings.
        if isinstance(reviewer_id, str) and reviewer_id.strip() and isinstance(asin, str) and asin.strip():
            pair = (reviewer_id.strip(), asin.strip())
            pair_counts[pair] += 1

            if pair not in first_pair_record:
                first_pair_record[pair] = record
            elif len(repeated_pair_examples) < sample_limit or pair in repeated_pair_examples:
                if pair not in repeated_pair_examples:
                    repeated_pair_examples[pair].append(first_pair_record[pair])
                repeated_pair_examples[pair].append(record)

        # Missing metadata is evaluated against a lookup containing a usable
        # non-empty title, because PURE needs a product name for its prompts.
        if isinstance(asin, str) and asin.strip() and asin.strip() not in title_lookup:
            normalized_asin = asin.strip()
            metadata_miss_count += 1
            metadata_miss_asins[normalized_asin] += 1
            if len(metadata_miss_examples) < sample_limit:
                metadata_miss_examples.append(record)

    repeated_pairs = {pair: count for pair, count in pair_counts.items() if count > 1}
    repeated_rows_beyond_first = sum(count - 1 for count in repeated_pairs.values())

    # Classify repeated pairs by whether the records appear to be exact copies
    # of the key fields used by our future processed dataset.
    exact_duplicate_pairs = 0
    differing_timestamp_pairs = 0
    differing_review_pairs = 0
    differing_rating_pairs = 0

    repeated_pair_set = set(repeated_pairs)
    grouped_key_values: Dict[Tuple[str, str], Dict[str, set[Any]]] = {
        pair: {
            "unixReviewTime": set(),
            "reviewText": set(),
            "overall": set(),
        }
        for pair in repeated_pair_set
    }

    for record in iter_json_gz(reviews_path):
        reviewer_id = record.get("reviewerID")
        asin = record.get("asin")
        if not isinstance(reviewer_id, str) or not isinstance(asin, str):
            continue

        pair = (reviewer_id.strip(), asin.strip())
        if pair not in repeated_pair_set:
            continue

        grouped_key_values[pair]["unixReviewTime"].add(record.get("unixReviewTime"))
        grouped_key_values[pair]["reviewText"].add(record.get("reviewText"))
        grouped_key_values[pair]["overall"].add(record.get("overall"))

    for values in grouped_key_values.values():
        timestamp_differs = len(values["unixReviewTime"]) > 1
        review_differs = len(values["reviewText"]) > 1
        rating_differs = len(values["overall"]) > 1

        if timestamp_differs:
            differing_timestamp_pairs += 1
        if review_differs:
            differing_review_pairs += 1
        if rating_differs:
            differing_rating_pairs += 1

        if not timestamp_differs and not review_differs and not rating_differs:
            exact_duplicate_pairs += 1

    print_heading("2. REVIEW REQUIRED-FIELD ANALYSIS")
    print(f"Total review records                     : {total_records}")
    print(f"Rows missing >=1 required PURE field     : {missing_required_count}")

    print_subheading(f"Missing-required examples (up to {sample_limit})")
    if not missing_required_examples:
        print("No missing-required review rows found.")
    else:
        for index, example in enumerate(missing_required_examples, start=1):
            print(
                f"\nExample {index} — missing={example['missing_fields']}\n"
                f"  {compact_json(example['record'])}"
            )

    print_heading("3. REVIEW-TO-METADATA MISS ANALYSIS")
    print(f"Review rows whose ASIN has no usable title: {metadata_miss_count}")
    print(f"Unique missing-title ASINs                : {len(metadata_miss_asins)}")

    print_subheading("Most frequent missing-title ASINs")
    for asin, count in metadata_miss_asins.most_common(sample_limit):
        print(f"  {asin}: {count} review row(s)")

    print_subheading(f"Metadata-miss review examples (up to {sample_limit})")
    if not metadata_miss_examples:
        print("No metadata misses found.")
    else:
        for index, record in enumerate(metadata_miss_examples, start=1):
            interesting = {
                "reviewerID": record.get("reviewerID"),
                "asin": record.get("asin"),
                "overall": record.get("overall"),
                "unixReviewTime": record.get("unixReviewTime"),
                "reviewText": record.get("reviewText"),
            }
            print(f"\nExample {index}: {compact_json(interesting)}")

    print_heading("4. REPEATED USER-ITEM ANALYSIS")
    print(f"Unique (user, item) pairs                 : {len(pair_counts)}")
    print(f"Pairs occurring more than once            : {len(repeated_pairs)}")
    print(f"Rows beyond first occurrence              : {repeated_rows_beyond_first}")
    print(f"Repeated pairs identical on key fields    : {exact_duplicate_pairs}")
    print(f"Repeated pairs with different timestamp   : {differing_timestamp_pairs}")
    print(f"Repeated pairs with different review text : {differing_review_pairs}")
    print(f"Repeated pairs with different rating      : {differing_rating_pairs}")

    print_subheading(f"Representative repeated user-item groups (up to {sample_limit})")
    if not repeated_pair_examples:
        print("No repeated user-item examples found.")
    else:
        for index, (pair, records) in enumerate(repeated_pair_examples.items(), start=1):
            reviewer_id, asin = pair
            print(
                f"\nExample {index} — reviewerID={reviewer_id}, ASIN={asin}, "
                f"shown_records={len(records)}"
            )
            for record_index, record in enumerate(records, start=1):
                interesting = {
                    "overall": record.get("overall"),
                    "verified": record.get("verified"),
                    "reviewText": record.get("reviewText"),
                    "summary": record.get("summary"),
                    "unixReviewTime": record.get("unixReviewTime"),
                }
                print(f"  Record {record_index}: {compact_json(interesting)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Inspect duplicate metadata records, repeated user-item reviews, "
            "missing required fields, and review-to-metadata misses."
        )
    )

    parser.add_argument(
        "--reviews",
        type=Path,
        default=Path("Video_Games_5.json.gz"),
        help="Path to Video_Games_5.json.gz (default: repository root).",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("meta_Video_Games.json.gz"),
        help="Path to meta_Video_Games.json.gz (default: repository root).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of representative examples to print per anomaly category.",
    )

    return parser.parse_args()


def main() -> None:
    """Run the diagnostic analysis."""

    args = parse_args()

    if args.samples < 1:
        raise ValueError("--samples must be at least 1")

    if not args.reviews.exists():
        raise FileNotFoundError(f"Reviews file not found: {args.reviews.resolve()}")

    if not args.metadata.exists():
        raise FileNotFoundError(f"Metadata file not found: {args.metadata.resolve()}")

    print("Scanning metadata anomalies...")
    _, title_lookup = analyze_metadata(args.metadata, args.samples)

    print("\nScanning review anomalies...")
    analyze_reviews(args.reviews, title_lookup, args.samples)

    print_heading("ANALYSIS COMPLETE")
    print(
        "No source data was modified.  Send this terminal output back before "
        "we freeze the preprocessing policy."
    )


if __name__ == "__main__":
    main()
