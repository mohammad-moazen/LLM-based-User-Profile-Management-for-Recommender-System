"""Run Phase 8 power planning and publish fatal errors through the handoff channel."""

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
from run_phase8_power_analysis import EXPERIMENT, main as run_main


def main() -> int:
    try:
        return run_main()
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
            commit_message="handoff: phase8 power analysis traceback",
            auto_push=True,
        )
        print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
