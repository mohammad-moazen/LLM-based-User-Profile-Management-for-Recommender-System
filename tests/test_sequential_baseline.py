"""Tests for the PURE-paper Sequential LLM baseline implementation."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.baselines import (
    build_sequential_messages,
    parse_complete_ranking,
    target_rank,
)


class SequentialBaselineTests(unittest.TestCase):
    def setUp(self):
        self.history = [
            {
                "user_id": "u1",
                "asin": "H1",
                "title": "First Product",
                "review_text": "SECRET REVIEW TEXT",
                "rating": 1.0,
                "timestamp": 1,
            },
            {
                "user_id": "u1",
                "asin": "H2",
                "title": "Second Product",
                "review_text": "ANOTHER SECRET REVIEW",
                "rating": 5.0,
                "timestamp": 2,
            },
        ]
        self.candidates = ["C1", "C2", "C3"]
        self.titles = {
            "C1": "Candidate One",
            "C2": "Candidate Two",
            "C3": "Candidate Three",
        }

    def test_prompt_uses_purchase_history_but_not_reviews_or_ratings(self):
        messages = build_sequential_messages(self.history, self.candidates, self.titles)
        prompt = messages[1]["content"]
        self.assertLess(prompt.index("First Product"), prompt.index("Second Product"))
        self.assertIn("H1", prompt)
        self.assertIn("H2", prompt)
        self.assertNotIn("SECRET REVIEW TEXT", prompt)
        self.assertNotIn("ANOTHER SECRET REVIEW", prompt)
        self.assertNotIn("1.0", prompt)
        self.assertNotIn("5.0", prompt)

    def test_complete_json_ranking_is_accepted(self):
        ranking = parse_complete_ranking(
            '{"ranking":["C2","C1","C3"]}',
            self.candidates,
        )
        self.assertEqual(ranking, ["C2", "C1", "C3"])
        self.assertEqual(target_rank(ranking, "C1"), 2)

    def test_markdown_fenced_json_is_accepted(self):
        ranking = parse_complete_ranking(
            '```json\n{"ranking":["C1","C2","C3"]}\n```',
            self.candidates,
        )
        self.assertEqual(ranking, self.candidates)

    def test_duplicate_or_incomplete_ranking_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_complete_ranking('{"ranking":["C1","C1","C3"]}', self.candidates)
        with self.assertRaises(ValueError):
            parse_complete_ranking('{"ranking":["C1","C2"]}', self.candidates)

    def test_unexpected_candidate_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_complete_ranking('{"ranking":["C1","C2","OTHER"]}', self.candidates)


if __name__ == "__main__":
    unittest.main()
