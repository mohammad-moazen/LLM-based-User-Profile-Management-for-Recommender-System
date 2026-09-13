"""Safe entrypoint for resumable Phase 10B2 Profile Updater recovery."""

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
from pure_recommender.phase10_profile_resume_context import build_resume_context
from pure_recommender.phase10_profile_resume_execute import resume_profile_updates
from pure_recommender.phase10_profile_resume_finalize import finalize_resume

EXPERIMENT = "phase10_confirmatory_profile_updater_resume_v1"


def _publish(payload: dict[str, object], message: str) -> None:
    ok, detail = publish_handoff(REPO_ROOT, payload, commit_message=message, auto_push=True)
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {detail}")


def main() -> int:
    try:
        ctx = build_resume_context(REPO_ROOT)
        print("=" * 100)
        print("PHASE 10B2 — RESUMABLE CONFIRMATORY PROFILE UPDATER")
        print("=" * 100)
        print(f"Existing latest successes : {ctx['ok_at_start']}")
        print(f"Existing latest errors    : {ctx['bad_at_start']}")
        print("Response repair            : NONE")
        print("Max Concurrent Predictions : 1")
        print()

        new_successes, new_calls, unresolved = resume_profile_updates(ctx)
        summary = finalize_resume(ctx, new_successes=new_successes, new_calls=new_calls)
        payload = {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "confirmatory_recommendation_outcomes_inspected": False,
            "summary": summary,
            "unresolved": unresolved,
        }
        _publish(payload, "handoff: phase10 Profile Updater resume " + ("pass" if summary["status"] == "PASS" else "incomplete"))
        return 0 if summary["status"] == "PASS" else 1
    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "confirmatory_recommendation_outcomes_inspected": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        _publish(payload, "handoff: phase10 Profile Updater resume error")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
