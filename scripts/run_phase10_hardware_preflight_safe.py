"""Safe wrapper for Phase 10A hardware preflight."""

from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys
import traceback


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.experiment_handoff import publish_handoff


EXPERIMENT = "phase10_hardware_preflight_v1"


def main() -> int:
    try:
        runpy.run_path(
            str(REPO_ROOT / "scripts" / "run_phase10_hardware_preflight.py"),
            run_name="__main__",
        )
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
        return code
    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "confirmatory_llm_calls": 0,
        }
        ok, message = publish_handoff(
            REPO_ROOT,
            payload,
            commit_message="handoff: phase10 hardware preflight error",
            auto_push=True,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
