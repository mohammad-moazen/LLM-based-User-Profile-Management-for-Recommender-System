"""Run Phase 10B1 Review Extractor against the frozen Phase 9 cohort.

The wrapper performs all confirmatory-design guards before delegating to the
already accepted Phase 3 Review Extractor implementation. It intentionally
reuses the exact extractor prompt/parser/grounding code from the frozen pilot
rather than creating a second implementation.
"""

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

from pure_recommender.analysis.hardware_preflight import verify_phase9_freeze
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.phase2 import load_histories, load_sessions
from pure_recommender.phase3 import build_required_extraction_tasks


EXPERIMENT = "phase10_confirmatory_review_extractor_v1"
EXPECTED_USERS = 150
EXPECTED_SESSIONS = 767
EXPECTED_EXTRACTIONS = 1067
COHORT_SHA256 = "72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca"
SESSIONS_SHA256 = "0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859"

COHORT_USERS_PATH = REPO_ROOT / "outputs" / "phase9_confirmatory_cohort_v1" / "cohort_users.json"
SESSIONS_PATH = REPO_ROOT / "outputs" / "phase9_confirmatory_cohort_v1" / "sessions.jsonl.gz"
COHORT_SUMMARY_PATH = REPO_ROOT / "outputs" / "phase9_confirmatory_cohort_v1" / "cohort_summary.json"
INTERACTIONS_PATH = REPO_ROOT / "outputs" / "phase1" / "interactions.jsonl.gz"
CONFIG_PATH = REPO_ROOT / "config" / "phase10_confirmatory_review_extractor.toml"
OUTPUT_DIR = REPO_ROOT / "outputs" / "phase10_confirmatory_review_extractor_v1"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"


def _publish(payload: dict[str, object], message: str) -> None:
    ok, detail = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=message,
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {detail}")


def _preflight() -> dict[str, object]:
    """Verify frozen cohort hashes and expected extraction workload."""

    freeze = verify_phase9_freeze(
        cohort_users_path=COHORT_USERS_PATH,
        sessions_path=SESSIONS_PATH,
        cohort_summary_path=COHORT_SUMMARY_PATH,
        expected_cohort_sha256=COHORT_SHA256,
        expected_sessions_sha256=SESSIONS_SHA256,
        expected_users=EXPECTED_USERS,
        expected_sessions=EXPECTED_SESSIONS,
    )

    histories = load_histories(INTERACTIONS_PATH)
    sessions = load_sessions(SESSIONS_PATH)
    tasks = build_required_extraction_tasks(histories, sessions)
    if len(tasks) != EXPECTED_EXTRACTIONS:
        raise RuntimeError(
            f"Frozen confirmatory workload mismatch: expected {EXPECTED_EXTRACTIONS} "
            f"Review Extractor tasks, found {len(tasks)}"
        )

    cohort_users = {str(session["user_id"]) for session in sessions}
    if len(cohort_users) != EXPECTED_USERS:
        raise RuntimeError(
            f"Expected {EXPECTED_USERS} confirmatory users in sessions, found {len(cohort_users)}"
        )

    return {
        **freeze,
        "required_extractions": len(tasks),
    }


def main() -> int:
    try:
        freeze = _preflight()
        print("=" * 100)
        print("PHASE 10B1 — CONFIRMATORY REVIEW EXTRACTOR")
        print("=" * 100)
        print(f"Phase 9 users verified      : {freeze['users']}")
        print(f"Phase 9 sessions verified   : {freeze['sessions']}")
        print(f"Required review extractions : {freeze['required_extractions']}")
        print(f"Cohort SHA256               : {freeze['cohort_sha256']}")
        print(f"Sessions SHA256             : {freeze['sessions_sha256']}")
        print("Runtime concurrency          : Max Concurrent Predictions = 1")
        print("Resume                       : ON")
        print()

        runner_path = REPO_ROOT / "scripts" / "run_phase3_review_extractor.py"
        previous_argv = sys.argv[:]
        exit_code = 0
        try:
            sys.argv = [
                str(runner_path),
                "--config",
                str(CONFIG_PATH),
                "--llm-config",
                str(REPO_ROOT / "config" / "local_llm.toml"),
            ]
            try:
                runpy.run_path(str(runner_path), run_name="__main__")
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 0
        finally:
            sys.argv = previous_argv

        if not SUMMARY_PATH.exists():
            raise RuntimeError(f"Review Extractor summary was not written: {SUMMARY_PATH}")
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        if not isinstance(summary, dict):
            raise RuntimeError("Review Extractor summary is not a JSON object")

        required = int(summary.get("required_unique_extractions", -1))
        successful = int(summary.get("successful_extractions", -1))
        failed = int(summary.get("failed_extractions", -1))
        underlying_status = str(summary.get("status", "UNKNOWN"))
        accepted = (
            exit_code == 0
            and underlying_status == "PASS"
            and required == EXPECTED_EXTRACTIONS
            and successful == EXPECTED_EXTRACTIONS
            and failed == 0
        )

        payload: dict[str, object] = {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "summary": {
                "status": "PASS" if accepted else "INCOMPLETE",
                "phase9_freeze": freeze,
                "runtime_max_concurrent_predictions": 1,
                "required_extractions": required,
                "successful_extractions": successful,
                "failed_extractions": failed,
                "source_summary": summary,
            },
        }
        _publish(
            payload,
            "handoff: phase10 confirmatory Review Extractor "
            + ("pass" if accepted else "incomplete"),
        )
        return 0 if accepted else 1

    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "note": "If failure occurred after delegation began, inspect the local resumable extraction artifact before retrying.",
        }
        _publish(payload, "handoff: phase10 confirmatory Review Extractor error")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
