"""Run Phase 7 analysis and publish a compact traceback if it fails."""

from __future__ import annotations

from pathlib import Path
import sys
import traceback


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pure_recommender.experiment_handoff import publish_handoff
from run_phase7_final_analysis import EXPERIMENT, main as run_main


def main() -> int:
    try:
        return run_main()
    except Exception as exc:
        # The traceback handoff is deliberately compact and contains no raw model
        # responses or private local files. It lets the remote collaborator debug
        # a failed analysis without accidentally committing the gitignored outputs.
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
            commit_message="handoff: phase7 final analysis traceback",
            auto_push=True,
        )
        print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
