"""Validated context builder for Phase 10B2 Profile Updater recovery."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from pure_recommender.analysis.hardware_preflight import verify_phase9_freeze
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase10_profile_resume import load_state_audit

EXPECTED_USERS = 150
EXPECTED_SESSIONS = 767
EXPECTED_UPDATES = 1067
MAX_RECOVERY_ATTEMPTS = 3
COHORT_SHA256 = "72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca"
SESSIONS_SHA256 = "0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859"


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return value


def _load_phase4_helpers(repo_root: Path):
    path = repo_root / "scripts" / "run_phase4_profile_updater_full.py"
    spec = importlib.util.spec_from_file_location("phase4_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load accepted Phase 4 helper functions")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_resume_context(repo_root: Path) -> dict[str, Any]:
    """Verify frozen inputs and return all objects required by the recovery loop."""
    cohort_users_path = repo_root / "outputs/phase9_confirmatory_cohort_v1/cohort_users.json"
    sessions_path = repo_root / "outputs/phase9_confirmatory_cohort_v1/sessions.jsonl.gz"
    cohort_summary_path = repo_root / "outputs/phase9_confirmatory_cohort_v1/cohort_summary.json"
    extractions_path = repo_root / "outputs/phase10_confirmatory_review_extractor_v1/extractions.jsonl"
    extractor_summary_path = repo_root / "outputs/phase10_confirmatory_review_extractor_v1/summary.json"
    output_dir = repo_root / "outputs/phase10_confirmatory_profile_updater_v1"
    states_path = output_dir / "profile_states.jsonl"
    summary_path = output_dir / "summary.json"

    freeze = verify_phase9_freeze(
        cohort_users_path=cohort_users_path,
        sessions_path=sessions_path,
        cohort_summary_path=cohort_summary_path,
        expected_cohort_sha256=COHORT_SHA256,
        expected_sessions_sha256=SESSIONS_SHA256,
        expected_users=EXPECTED_USERS,
        expected_sessions=EXPECTED_SESSIONS,
    )
    extractor = _load_json(extractor_summary_path)
    if str(extractor.get("status")) != "PASS":
        raise RuntimeError("Phase 10B1 Review Extractor is not PASS")
    if int(extractor.get("successful_extractions", -1)) != EXPECTED_UPDATES:
        raise RuntimeError("Phase 10B1 extraction count does not match the frozen design")

    phase4 = _load_phase4_helpers(repo_root)
    extraction_rows = phase4._load_extractions(extractions_path)
    grouped = phase4._group_and_validate_prefixes(extraction_rows)
    if len(grouped) != EXPECTED_USERS or len(extraction_rows) != EXPECTED_UPDATES:
        raise RuntimeError("Frozen confirmatory Profile Updater workload mismatch")

    latest, recovery_attempts, rows_at_start = load_state_audit(states_path)
    ok_at_start = sum(row.get("status") == "ok" for row in latest.values())
    bad_at_start = sum(row.get("status") != "ok" for row in latest.values())
    if ok_at_start < 225:
        raise RuntimeError(f"Expected at least 225 audited successful states; found {ok_at_start}")

    llm_cfg = load_local_llm_config(repo_root / "config/local_llm.toml")
    client = OpenAICompatibleLLMClient(base_url=llm_cfg.base_url, timeout_seconds=llm_cfg.timeout_seconds)
    if llm_cfg.model not in client.list_models():
        raise RuntimeError(f"Configured model {llm_cfg.model!r} is not exposed by local server")

    return {
        "freeze": freeze,
        "phase4": phase4,
        "grouped": grouped,
        "latest": latest,
        "recovery_attempts": recovery_attempts,
        "rows_at_start": rows_at_start,
        "ok_at_start": ok_at_start,
        "bad_at_start": bad_at_start,
        "llm_cfg": llm_cfg,
        "client": client,
        "states_path": states_path,
        "summary_path": summary_path,
    }


__all__ = [
    "EXPECTED_UPDATES",
    "EXPECTED_USERS",
    "MAX_RECOVERY_ATTEMPTS",
    "build_resume_context",
]
