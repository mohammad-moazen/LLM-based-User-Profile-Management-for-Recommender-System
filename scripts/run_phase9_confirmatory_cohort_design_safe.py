"""Safe wrapper for Phase 9 confirmatory cohort design."""
from __future__ import annotations

import traceback
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC_DIR = REPO_ROOT / "src"
for path in (SCRIPTS_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pure_recommender.experiment_handoff import publish_handoff
import run_phase9_confirmatory_cohort_design as runner


if __name__ == "__main__":
    try:
        raise SystemExit(runner.main())
    except SystemExit:
        raise
    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": runner.EXPERIMENT,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        ok, message = publish_handoff(
            REPO_ROOT,
            payload,
            commit_message="handoff: phase9 cohort design error",
            auto_push=True,
        )
        print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
        raise
