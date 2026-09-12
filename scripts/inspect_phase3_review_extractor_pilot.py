"""Inspect Review Extractor pilot outputs against their source reviews.

This helper performs no inference and does not modify experiment artifacts. It
prints the canonical input review beside the latest stored extraction so the
pilot can be checked for semantic grounding before enabling all Phase 3 tasks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.phase2 import load_histories, load_sessions
from pure_recommender.phase3 import build_required_extraction_tasks, load_phase3_config


def _load_latest_results(path: Path) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    if not path.exists():
        raise FileNotFoundError(f"Phase 3 extraction results not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if isinstance(row, dict) and isinstance(row.get("task_id"), str):
                latest[row["task_id"]] = row
    return latest


def _print_list(label: str, values: object) -> None:
    print(f"{label}:")
    if not isinstance(values, list) or not values:
        print("  - <empty>")
        return
    for value in values:
        print(f"  - {value}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print source reviews beside Phase 3 Review Extractor pilot outputs"
    )
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase3_review_extractor.toml"),
        help="Path to the Phase 3 Review Extractor TOML config",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Number of required extraction tasks to inspect (default: 3)",
    )
    args = parser.parse_args()

    if args.limit < 1:
        raise ValueError("--limit must be >= 1")

    config = load_phase3_config(args.config)
    histories = load_histories(config.input.interactions_path)
    sessions = load_sessions(config.input.sessions_path)
    tasks = build_required_extraction_tasks(histories, sessions)[: args.limit]

    results_path = config.output.directory / "extractions.jsonl"
    latest_results = _load_latest_results(results_path)

    print("=" * 96)
    print("PHASE 3 REVIEW EXTRACTOR — QUALITATIVE PILOT INSPECTION")
    print("=" * 96)
    print(f"results: {results_path}")
    print(f"tasks inspected: {len(tasks)}")

    for ordinal, task in enumerate(tasks, start=1):
        interaction = task.interaction
        row = latest_results.get(task.task_id)

        print("\n" + "-" * 96)
        print(f"REVIEW {ordinal}/{len(tasks)}")
        print("-" * 96)
        print(f"task_id : {task.task_id}")
        print(f"user_id : {task.user_id}")
        print(f"position: {task.interaction_position}")
        print(f"asin    : {interaction.get('asin')}")
        print(f"title   : {interaction.get('title')}")
        print(f"rating  : {interaction.get('rating')}")
        print("\nSOURCE REVIEW:")
        print(str(interaction.get("review_text", "")))

        if row is None:
            print("\nEXTRACTION: <missing result>")
            continue
        if row.get("status") != "ok":
            print(f"\nEXTRACTION ERROR: {row.get('error', '<unknown>')}")
            continue

        extraction = row.get("extraction")
        if not isinstance(extraction, dict):
            print("\nEXTRACTION: <invalid stored structure>")
            continue

        print("\nEXTRACTED REPRESENTATION:")
        _print_list("likes", extraction.get("likes"))
        _print_list("dislikes", extraction.get("dislikes"))
        _print_list("key_features", extraction.get("key_features"))

    print("\n" + "=" * 96)
    print("Inspection only: no model calls and no experiment files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
