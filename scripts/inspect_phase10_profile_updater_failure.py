"""Inspect the local Phase 10B2 Profile Updater failure without making any LLM call.

The confirmatory Profile Updater stopped after one failed task. This diagnostic
reads the local ignored artifact, extracts the exact failed task/error/raw output,
and publishes only a compact diagnostic handoff. It does not modify profiles,
rerun the model, or inspect recommendation outcomes.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.experiment_handoff import publish_handoff

EXPERIMENT = "phase10_confirmatory_profile_updater_diagnostic_v1"
STATES_PATH = REPO_ROOT / "outputs" / "phase10_confirmatory_profile_updater_v1" / "profile_states.jsonl"
SUMMARY_PATH = REPO_ROOT / "outputs" / "phase10_confirmatory_profile_updater_v1" / "summary.json"


def _read_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}")
            rows.append(value)
    return rows


def main() -> int:
    rows = _read_rows(STATES_PATH)
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8")) if SUMMARY_PATH.exists() else {}

    errors = [row for row in rows if row.get("status") == "error"]
    oks = [row for row in rows if row.get("status") == "ok"]
    if not errors:
        raise RuntimeError("No error row found in the local Phase 10B2 state artifact")

    compact_errors: list[dict[str, object]] = []
    for row in errors[-5:]:
        raw = row.get("raw_response")
        raw_text = raw if isinstance(raw, str) else ""
        compact_errors.append(
            {
                "task_id": row.get("task_id"),
                "user_id": row.get("user_id"),
                "interaction_position": row.get("interaction_position"),
                "error": row.get("error"),
                "latency_seconds": row.get("latency_seconds"),
                "raw_response_prefix": raw_text[:2500],
                "raw_response_length": len(raw_text),
            }
        )

    previous_ok = oks[-1] if oks else {}
    payload = {
        "state": "DIAGNOSTIC",
        "experiment": EXPERIMENT,
        "confirmatory_recommendation_outcomes_inspected": False,
        "llm_calls_made": 0,
        "rows_total": len(rows),
        "ok_rows": len(oks),
        "error_rows": len(errors),
        "summary_status": summary.get("status") if isinstance(summary, dict) else None,
        "latest_errors": compact_errors,
        "previous_success": {
            "task_id": previous_ok.get("task_id"),
            "user_id": previous_ok.get("user_id"),
            "interaction_position": previous_ok.get("interaction_position"),
            "finish_reason": previous_ok.get("finish_reason"),
        },
    }

    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message="handoff: phase10 profile updater failure diagnostic",
        auto_push=True,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
