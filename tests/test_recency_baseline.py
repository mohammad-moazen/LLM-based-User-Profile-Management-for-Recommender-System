"""Tests for the PURE Recency-Focused LLM baseline."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.baselines import build_recency_messages, parse_complete_ranking


class RecencyBaselineTests(unittest.TestCase):
    def setUp(self):
        self.history = [
            {
                "user_id": "u1",
                "asin": "H1",
                "title": "Older Product",
                "review_text": "SECRET OLD REVIEW",
                "rating": 2.0,
                "timestamp": 1,
            },
            {
                "user_id": "u1",
                "asin": "H2",
                "title": "Most Recent Product",
                "review_text": "SECRET RECENT REVIEW",
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

    def test_prompt_explicitly_emphasizes_most_recent_purchase(self):
        messages = build_recency_messages(self.history, self.candidates, self.titles)
        prompt = messages[1]["content"]
        self.assertIn("Note that my most recently purchased item is: Most Recent Product.", prompt)
        self.assertIn("Give this recent purchase special emphasis", prompt)
        self.assertLess(prompt.index("Older Product"), prompt.index("Most Recent Product"))

    def test_prompt_does_not_expose_reviews_ratings_or_asins(self):
        messages = build_recency_messages(self.history, self.candidates, self.titles)
        prompt = messages[1]["content"]
        self.assertNotIn("SECRET OLD REVIEW", prompt)
        self.assertNotIn("SECRET RECENT REVIEW", prompt)
        self.assertNotIn("H1", prompt)
        self.assertNotIn("H2", prompt)
        self.assertNotIn("C1", prompt)
        self.assertNotIn("C2", prompt)
        self.assertNotIn("2.0", prompt)
        self.assertNotIn("5.0", prompt)

    def test_shared_numbered_parser_maps_back_to_frozen_asins(self):
        ranking = parse_complete_ranking('{"ranking":[3,1,2]}', self.candidates)
        self.assertEqual(ranking, ["C3", "C1", "C2"])


if __name__ == "__main__":
    unittest.main()
