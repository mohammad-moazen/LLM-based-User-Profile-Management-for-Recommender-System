"""Tests for leakage-safe Phase 3 review extraction task construction."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.phase3 import build_required_extraction_tasks


class Phase3ReviewTaskTests(unittest.TestCase):
    def setUp(self):
        self.history = [
            {
                "user_id": "u1",
                "asin": f"A{position}",
                "title": f"Product {position}",
                "review_text": f"Review {position}",
                "rating": 5.0,
                "timestamp": position,
            }
            for position in range(1, 6)
        ]
        self.histories = {"u1": self.history}

    def test_first_target_at_position_four_requires_only_first_three_reviews(self):
        sessions = [
            {
                "session_id": "u1:4",
                "user_id": "u1",
                "target_position": 4,
                "target_asin": "A4",
                "candidate_asins": ["A4", "X1"],
            }
        ]
        tasks = build_required_extraction_tasks(self.histories, sessions)
        self.assertEqual([task.interaction_position for task in tasks], [1, 2, 3])
        self.assertNotIn("A4", [task.interaction["asin"] for task in tasks])

    def test_later_session_adds_newly_observed_previous_target_once(self):
        sessions = [
            {
                "session_id": "u1:4",
                "user_id": "u1",
                "target_position": 4,
                "target_asin": "A4",
                "candidate_asins": ["A4", "X1"],
            },
            {
                "session_id": "u1:5",
                "user_id": "u1",
                "target_position": 5,
                "target_asin": "A5",
                "candidate_asins": ["A5", "X2"],
            },
        ]
        tasks = build_required_extraction_tasks(self.histories, sessions)
        self.assertEqual([task.interaction_position for task in tasks], [1, 2, 3, 4])
        self.assertEqual(len({task.task_id for task in tasks}), 4)
        self.assertNotIn("A5", [task.interaction["asin"] for task in tasks])

    def test_target_mismatch_fails_loudly(self):
        sessions = [
            {
                "session_id": "u1:4",
                "user_id": "u1",
                "target_position": 4,
                "target_asin": "WRONG",
                "candidate_asins": ["WRONG", "X1"],
            }
        ]
        with self.assertRaises(ValueError):
            build_required_extraction_tasks(self.histories, sessions)


if __name__ == "__main__":
    unittest.main()
