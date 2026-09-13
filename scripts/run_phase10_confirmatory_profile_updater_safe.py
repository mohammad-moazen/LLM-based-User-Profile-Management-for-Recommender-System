"""Run Phase 10B2 Profile Updater on the frozen confirmatory evidence stream."""

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

EXPERIMENT = "phase10_confirmatory_profile_updater_v1"
EXPECTED_USERS = 150
EXPECTED_SESSIONS = 767
EXPECTED_UPDATES = 1067
COHORT_SHA256 = "72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca"
SESSIONS_SHA256 = "0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859"

COHORT_USERS_PATH = REPO_ROOT / "outputs" / "phase9_confirmatory_cohort_v1" / "cohort_users.json"
SESSIONS_PATH = REPO_ROOT / "outputs" / "phase9_confirmatory_cohort_v1" / "sessions.jsonl.gz"
COHORT_SUMMARY_PATH = REPO_ROOT / "outputs" / "phase9_confirmatory_cohort_v1" / "cohort_summary.json"
EXTRACTOR_SUMMARY_PATH = REPO_ROOT / "outputs" / "phase10_confirmatory_review_extractor_v1" / "summary.json"
EXTRACTIONS_PATH = REPO_ROOT / "outputs" / "phase10_confirmatory_review_extractor_v1" / "extractions.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "phase10_confirmatory_profile_updater.toml"
OUTPUT_DIR = REPO_ROOT / "outputs" / "phase10_confirmatory_profile_updater_v1"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"


def _publish(payload: dict[str, object], message: str) -> None:
    ok, detail = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=message,
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {detail}")


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return value


def _preflight() -> dict[str, object]:
    freeze = verify_phase9_freeze(
        cohort_users_path=COHORT_USERS_PATH,
        sessions_path=SESSIONS_PATH,
        cohort_summary_path=COHORT_SUMMARY_PATH,
        expected_cohort_sha256=COHORT_SHA256,
        expected_sessions_sha256=SESSIONS_SHA256,
        expected_users=EXPECTED_USERS,
        expected_sessions=EXPECTED_SESSIONS,
    )

    extractor = _load_json(EXTRACTOR_SUMMARY_PATH)
    if str(extractor.get("status")) != "PASS":
        raise RuntimeError("Phase 10B1 Review Extractor is not PASS")
    if int(extractor.get("required_unique_extractions", -1)) != EXPECTED_UPDATES:
        raise RuntimeError("Unexpected Phase 10B1 required extraction count")
    if int(extractor.get("successful_extractions", -1)) != EXPECTED_UPDATES:
        raise RuntimeError("Phase 10B1 successful extraction count mismatch")
    if int(extractor.get("failed_extractions", -1)) != 0:
        raise RuntimeError("Phase 10B1 contains failed extraction tasks")
    if int(extractor.get("users_in_successful_extractions", -1)) != EXPECTED_USERS:
        raise RuntimeError("Phase 10B1 user count mismatch")
    if not EXTRACTIONS_PATH.exists():
        raise FileNotFoundError(EXTRACTIONS_PATH)

    generation = extractor.get("generation")
    if not isinstance(generation, dict):
        raise RuntimeError("Phase 10B1 summary has no generation block")
    if generation.get("temperature") != 0.0 or generation.get("max_tokens") != 1024 or generation.get("seed") != 42:
        raise RuntimeError("Phase 10B1 generation settings do not match the frozen protocol")

    return {**freeze, "source_extractions": EXPECTED_UPDATES}


def main() -> int:
    try:
        freeze = _preflight()
        print("=" * 100)
        print("PHASE 10B2 — CONFIRMATORY PROFILE UPDATER")
        print("=" * 100)
        print(f"Phase 9 users verified       : {freeze['users']}")
        print(f"Phase 9 sessions verified    : {freeze['sessions']}")
        print(f"Source extractions verified  : {freeze['source_extractions']}")
        print(f"Cohort SHA256                : {freeze['cohort_sha256']}")
        print(f"Sessions SHA256              : {freeze['sessions_sha256']}")
        print("Runtime concurrency           : Max Concurrent Predictions = 1")
        print("Updater implementation        : accepted Phase 4 v4 + retention guard")
        print()

        runner_path = REPO_ROOT / "scripts" / "run_phase4_profile_updater_full.py"
        old_argv = sys.argv[:]
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
            sys.argv = old_argv

        summary = _load_json(SUMMARY_PATH)
        expected = int(summary.get("expected_updates", -1))
        successful = int(summary.get("successful_updates", -1))
        failed = int(summary.get("failed_updates", -1))
        users = int(summary.get("users", -1))
        accepted = (
            exit_code == 0
            and str(summary.get("status")) == "PASS"
            and users == EXPECTED_USERS
            and expected == EXPECTED_UPDATES
            and successful == EXPECTED_UPDATES
            and failed == 0
        )

        payload: dict[str, object] = {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "summary": {
                "status": "PASS" if accepted else "INCOMPLETE",
                "phase9_freeze": freeze,
                "runtime_max_concurrent_predictions": 1,
                "users": users,
                "expected_updates": expected,
                "successful_updates": successful,
                "failed_updates": failed,
                "source_summary": summary,
            },
        }
        _publish(
            payload,
            "handoff: phase10 confirmatory Profile Updater " + ("pass" if accepted else "incomplete"),
        )
        return 0 if accepted else 1
    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        _publish(payload, "handoff: phase10 confirmatory Profile Updater error")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
