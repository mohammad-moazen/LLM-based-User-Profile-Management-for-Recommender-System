"""Run Phase 3 Review Extractor and enrich failed handoffs with full traceback.

The main Phase 3 runner already publishes compact RESULT/ERROR payloads. This
wrapper adds the complete Python traceback to ``handoff/latest.json`` when an
unexpected exception escapes the runner, so terminal tracebacks no longer need
to be copied manually into chat.
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

from pure_recommender.experiment_handoff import publish_handoff
from run_phase3_review_extractor import main as run_phase3_main


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
        return run_phase3_main()
    except Exception as exc:
        payload = _load_existing_handoff()
        payload.update(
            {
                "state": "ERROR",
                "experiment": "phase3_review_extractor",
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        ok, message = publish_handoff(
            REPO_ROOT,
            payload,
            commit_message="handoff: phase3 review extractor traceback",
            auto_push=True,
        )
        label = "HANDOFF" if ok else "HANDOFF WARNING"
        print(f"{label}: {message}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
