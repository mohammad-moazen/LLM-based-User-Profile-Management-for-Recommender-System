from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from pure_recommender.phase10_profile_resume import aggregate_latest_states, load_state_audit


class Phase10ProfileResumeTests(unittest.TestCase):
    def test_load_state_audit_keeps_latest_row_and_attempt_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "states.jsonl"
            rows = [
                {"task_id": "U:1", "status": "error", "recovery_attempt": 1},
                {"task_id": "U:1", "status": "ok", "recovery_attempt": 2},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            latest, attempts, total = load_state_audit(path)
            self.assertEqual(total, 2)
            self.assertEqual(latest["U:1"]["status"], "ok")
            self.assertEqual(attempts["U:1"], 2)

    def test_aggregate_latest_states_ignores_superseded_failure(self) -> None:
        latest = {
            "U:1": {
                "task_id": "U:1",
                "status": "ok",
                "latency_seconds": 1.5,
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
                "guard_restored_entries": {"likes": ["a"]},
                "guard_allowed_removals": {},
            }
        }
        summary = aggregate_latest_states(latest)
        self.assertEqual(summary["successful_updates"], 1)
        self.assertEqual(summary["failed_updates"], 0)
        self.assertEqual(summary["usage_totals"]["total_tokens"], 12)


if __name__ == "__main__":
    unittest.main()
