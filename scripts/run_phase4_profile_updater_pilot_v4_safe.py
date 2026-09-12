"""Run Profile Updater pilot v4 using the shared pilot engine.

The shared runner remains the chronological execution engine. This wrapper gives
v4 its own handoff identity and durable local summary while using the v4
information-preserving retention guard exported by ``pure_recommender.pure``.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import traceback

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.phase4 import load_phase4_config
import run_phase4_profile_updater_pilot as shared_runner

EXPERIMENT = "phase4_profile_updater_pilot_v4"
VALIDATION = "same_category_id_selection_plus_information_preserving_dominance_guard"
DELETION_POLICY = "remove_only_exact_duplicates_or_overlaps_dominated_by_richer_same_category_evidence"


def _publish_v4(payload: dict[str, object], status_word: str) -> None:
    payload["experiment"] = EXPERIMENT
    summary = payload.get("summary")
    if isinstance(summary, dict):
        summary["pilot_version"] = "v4"
        summary["validation"] = VALIDATION
        summary["deletion_policy"] = DELETION_POLICY

    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: phase4 profile updater pilot v4 {status_word.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def _rewrite_local_summary() -> None:
    config = load_phase4_config(REPO_ROOT / "config" / "phase4_profile_updater_pilot.toml")
    summary_path = config.output.directory / "summary.json"
    if not summary_path.exists():
        return
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    payload["pilot_version"] = "v4"
    payload["validation"] = VALIDATION
    payload["deletion_policy"] = DELETION_POLICY
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    shared_runner._publish = _publish_v4
    try:
        result = shared_runner.main()
        _rewrite_local_summary()
        return result
    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc(),
        }
        ok, message = publish_handoff(
            REPO_ROOT,
            payload,
            commit_message="handoff: phase4 profile updater pilot v4 traceback",
            auto_push=True,
        )
        print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
