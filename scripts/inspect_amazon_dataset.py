"""Inspect Amazon Review 2018 JSON.GZ files without extracting them.

This utility reads a small number of records from the review and metadata files,
prints their top-level schema, Python value types, missing/null counts, and a few
sample records. It intentionally uses only the Python standard library so it can
be executed before the project's dependencies are installed.

Run from the repository root:

    python scripts/inspect_amazon_dataset.py

Or provide explicit file paths:

    python scripts/inspect_amazon_dataset.py \
        --reviews "D:/path/to/Video_Games_5.json.gz" \
        --metadata "D:/path/to/meta_Video_Games.json.gz"
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


DEFAULT_REVIEWS = "Video_Games_5.json.gz"
DEFAULT_METADATA = "meta_Video_Games.json.gz"


def iter_json_lines(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield JSON objects from a gzip-compressed JSON Lines file."""
    with gzip.open(path, mode="rt", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in {path} at line {line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected a JSON object in {path} at line {line_number}, "
                    f"but found {type(record).__name__}."
                )

            yield record


def type_name(value: Any) -> str:
    """Return a compact, human-readable type description for a value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        if not value:
            return "list[empty]"
        child_types = sorted({type_name(item) for item in value[:10]})
        return f"list[{', '.join(child_types)}]"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def inspect_file(path: Path, scan_records: int, sample_records: int) -> None:
    """Inspect a JSON.GZ dataset file and print a compact schema report."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    key_counts: Counter[str] = Counter()
    null_counts: Counter[str] = Counter()
    observed_types: Dict[str, Counter[str]] = defaultdict(Counter)
    samples: List[Dict[str, Any]] = []
    rows_read = 0

    for record in iter_json_lines(path):
        rows_read += 1

        if len(samples) < sample_records:
            samples.append(record)

        for key, value in record.items():
            key_counts[key] += 1
            observed_types[key][type_name(value)] += 1
            if value is None:
                null_counts[key] += 1

        if rows_read >= scan_records:
            break

    print("=" * 100)
    print(f"FILE: {path}")
    print(f"SIZE: {path.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"RECORDS SCANNED: {rows_read}")
    print("-" * 100)
    print("SCHEMA")

    for key in sorted(key_counts):
        types = ", ".join(
            f"{name} ({count})" for name, count in observed_types[key].most_common()
        )
        missing = rows_read - key_counts[key]
        nulls = null_counts[key]
        print(
            f"{key:<25} types=[{types}]  "
            f"missing={missing:<5} null={nulls:<5}"
        )

    print("-" * 100)
    print(f"FIRST {len(samples)} SAMPLE RECORD(S)")

    for index, sample in enumerate(samples, start=1):
        print(f"\nSample {index}:")
        print(json.dumps(sample, ensure_ascii=False, indent=2))

    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Amazon Review 2018 review and metadata JSON.GZ files."
    )
    parser.add_argument(
        "--reviews",
        type=Path,
        default=Path(DEFAULT_REVIEWS),
        help=f"Path to review file (default: {DEFAULT_REVIEWS}).",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path(DEFAULT_METADATA),
        help=f"Path to metadata file (default: {DEFAULT_METADATA}).",
    )
    parser.add_argument(
        "--scan-records",
        type=int,
        default=1000,
        help="Number of records to scan from each file for schema inference.",
    )
    parser.add_argument(
        "--sample-records",
        type=int,
        default=2,
        help="Number of complete sample records to print from each file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    inspect_file(
        path=args.reviews,
        scan_records=args.scan_records,
        sample_records=args.sample_records,
    )
    inspect_file(
        path=args.metadata,
        scan_records=args.scan_records,
        sample_records=args.sample_records,
    )


if __name__ == "__main__":
    main()
