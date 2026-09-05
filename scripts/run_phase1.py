"""Build and validate the Phase 1 data/evaluation foundation.

Run from the repository root:

    python scripts/run_phase1.py
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.config import load_phase1_config
from pure_recommender.data.preprocessing import build_canonical_dataset
from pure_recommender.data.sessions import (
    build_recommendation_sessions,
    group_histories,
    select_eligible_users,
    validate_sessions,
)


def _write_jsonl_gz(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def _print_first_session(session, histories, item_titles) -> None:
    history = histories[session.user_id]
    target_index = session.target_position - 1
    print("\n" + "=" * 88)
    print("FIRST GENERATED SESSION")
    print("=" * 88)
    print(f"session_id : {session.session_id}")
    print(f"user_id    : {session.user_id}")
    print("\nObserved history:")
    for index, row in enumerate(history[:target_index], start=1):
        print(f"  {index:02d}. {row.title} [{row.asin}]")
    print("\nTarget:")
    print(f"  {history[target_index].title} [{session.target_asin}]")
    print("\nCandidates:")
    for index, asin in enumerate(session.candidate_asins, start=1):
        marker = "  <-- TARGET" if asin == session.target_asin else ""
        print(f"  {index:02d}. {item_titles[asin]} [{asin}]{marker}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PURE Phase 1 preprocessing and session generation")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase1.toml"),
        help="Path to Phase 1 TOML config",
    )
    args = parser.parse_args()

    config = load_phase1_config(args.config)
    for label, path in (("reviews", config.data.reviews_path), ("metadata", config.data.metadata_path)):
        if not path.exists():
            raise FileNotFoundError(f"{label} file not found: {path}")

    print("Building canonical dataset...")
    interactions, item_titles, report = build_canonical_dataset(
        reviews_path=config.data.reviews_path,
        metadata_path=config.data.metadata_path,
        min_history=config.experiment.min_history,
    )

    print("Building chronological histories...")
    histories = group_histories(interactions)
    selected_users = select_eligible_users(
        histories=histories,
        min_history=config.experiment.min_history,
        max_users=config.experiment.max_users,
        selection_seed=config.experiment.user_selection_seed,
    )

    print("Generating deterministic candidate sets...")
    sessions = build_recommendation_sessions(
        histories=histories,
        item_universe=item_titles.keys(),
        selected_users=selected_users,
        min_history=config.experiment.min_history,
        candidate_size=config.experiment.candidate_size,
        candidate_seed=config.experiment.candidate_seed,
    )
    validate_sessions(sessions, histories, config.experiment.candidate_size)

    output_dir = config.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)

    if config.output.write_items:
        _write_jsonl_gz(
            output_dir / "items.jsonl.gz",
            ({"asin": asin, "title": title} for asin, title in sorted(item_titles.items())),
        )
    if config.output.write_interactions:
        _write_jsonl_gz(
            output_dir / "interactions.jsonl.gz",
            (row.to_public_dict() for row in interactions),
        )
    if config.output.write_sessions:
        _write_jsonl_gz(
            output_dir / "sessions.jsonl.gz",
            (session.to_dict() for session in sessions),
        )

    report_payload = {
        "preprocessing": report.to_dict(),
        "experiment": {
            "min_history": config.experiment.min_history,
            "candidate_size": config.experiment.candidate_size,
            "candidate_seed": config.experiment.candidate_seed,
            "user_selection_seed": config.experiment.user_selection_seed,
            "max_users": config.experiment.max_users,
            "selected_users": len(selected_users),
            "generated_sessions": len(sessions),
        },
        "validation": {
            "candidate_invariants": "PASS",
            "chronological_histories": "PASS",
        },
    }
    with (output_dir / "phase1_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report_payload, handle, indent=2, ensure_ascii=False)

    print("\n" + "=" * 88)
    print("PURE PHASE 1 REPORT")
    print("=" * 88)
    for key, value in report.to_dict().items():
        print(f"{key:40s}: {value}")
    print(f"{'selected_users':40s}: {len(selected_users)}")
    print(f"{'generated_sessions':40s}: {len(sessions)}")
    print(f"{'candidate_size':40s}: {config.experiment.candidate_size}")
    print(f"{'candidate_seed':40s}: {config.experiment.candidate_seed}")
    print(f"{'candidate_invariants':40s}: PASS")
    print(f"{'output_directory':40s}: {output_dir}")

    if sessions:
        _print_first_session(sessions[0], histories, item_titles)

    print("\nPhase 1 pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
