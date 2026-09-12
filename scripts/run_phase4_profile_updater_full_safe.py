"""Run the full Phase 4 Profile Updater and publish fatal tracebacks safely."""

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
from run_phase4_profile_updater_full import EXPERIMENT, main as run_full_main


def _load_existing_handoff() -> dict[str, object]:
    path = REPO_ROOT / "handoff" / "latest.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    try:
        return run_full_main()
    except Exception as exc:
        payload = _load_existing_handoff()
        payload.update(
            {
                "state": "ERROR",
                "experiment": EXPERIMENT,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        ok, message = publish_handoff(
            REPO_ROOT,
            payload,
            commit_message="handoff: phase4 full profile updater traceback",
            auto_push=True,
        )
        print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
