"""Tests for deterministic Phase 9 confirmatory cohort design helpers."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis.confirmatory_cohort import (
    build_confirmatory_sessions,
    cohort_user_records,
    eligible_user_order,
    select_new_confirmatory_users,
    validate_confirmatory_sessions,
)


def _row(user_id: str, asin: str) -> dict[str, object]:
    return {"user_id": user_id, "asin": asin, "title": asin}


class ConfirmatoryCohortTests(unittest.TestCase):
    def setUp(self):
        self.histories = {
            "u1": [_row("u1", f"u1_{i}") for i in range(5)],
            "u2": [_row("u2", f"u2_{i}") for i in range(4)],
            "u3": [_row("u3", f"u3_{i}") for i in range(6)],
            "u4": [_row("u4", f"u4_{i}") for i in range(5)],
            "too_short": [_row("too_short", f"s_{i}") for i in range(3)],
        }

    def test_new_cohort_is_next_deterministic_users_after_pilot(self):
        ordered = eligible_user_order(self.histories, min_history=3, selection_seed=123)
        pilot = ordered[:2]
        selected, ordered_again = select_new_confirmatory_users(
            self.histories,
            pilot_user_ids=pilot,
            expected_pilot_users=2,
            new_users=2,
            min_history=3,
            selection_seed=123,
        )
        self.assertEqual(ordered_again, ordered)
        self.assertEqual(selected, ordered[2:4])
        self.assertTrue(set(selected).isdisjoint(pilot))

    def test_selection_fails_if_pilot_is_not_frozen_prefix(self):
        ordered = eligible_user_order(self.histories, min_history=3, selection_seed=123)
        wrong_pilot = [ordered[0], ordered[2]]
        with self.assertRaises(ValueError):
            select_new_confirmatory_users(
                self.histories,
                pilot_user_ids=wrong_pilot,
                expected_pilot_users=2,
                new_users=1,
                min_history=3,
                selection_seed=123,
            )

    def test_session_generation_is_deterministic_and_leakage_free(self):
        selected = ["u1"]
        item_universe = {
            *(row["asin"] for rows in self.histories.values() for row in rows),
            *(f"neg_{i}" for i in range(30)),
        }
        first = build_confirmatory_sessions(
            self.histories,
            item_universe=item_universe,
            selected_users=selected,
            min_history=3,
            candidate_size=5,
            candidate_seed=42,
        )
        second = build_confirmatory_sessions(
            self.histories,
            item_universe=item_universe,
            selected_users=selected,
            min_history=3,
            candidate_size=5,
            candidate_seed=42,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        validate_confirmatory_sessions(
            first,
            self.histories,
            selected_users=selected,
            min_history=3,
            candidate_size=5,
        )
        interacted = {str(row["asin"]) for row in self.histories["u1"]}
        for session in first:
            negatives = set(session["candidate_asins"]) - {session["target_asin"]}
            self.assertTrue(negatives.isdisjoint(interacted))

    def test_user_records_count_sessions_and_profile_events(self):
        ordered = eligible_user_order(self.histories, min_history=3, selection_seed=123)
        selected = ordered[:2]
        records = cohort_user_records(selected, ordered, self.histories, min_history=3)
        for record in records:
            length = int(record["history_length"])
            self.assertEqual(int(record["recommendation_sessions"]), length - 3)
            self.assertEqual(int(record["profile_evidence_events"]), length - 1)


if __name__ == "__main__":
    unittest.main()
