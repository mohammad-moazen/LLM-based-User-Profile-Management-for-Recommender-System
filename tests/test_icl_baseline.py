"""Tests for the PURE In-Context Learning (ICL) LLM baseline."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.baselines import build_icl_messages, parse_complete_ranking


class ICLBaselineTests(unittest.TestCase):
    def setUp(self):
        self.history = [
            {
                "user_id": "u1",
                "asin": "H1",
                "title": "Old Product One",
                "review_text": "SECRET REVIEW ONE",
                "rating": 2.0,
                "timestamp": 1,
            },
            {
                "user_id": "u1",
                "asin": "H2",
                "title": "Old Product Two",
                "review_text": "SECRET REVIEW TWO",
                "rating": 4.0,
                "timestamp": 2,
            },
            {
                "user_id": "u1",
                "asin": "H3",
                "title": "Demonstrated Recent Product",
                "review_text": "SECRET RECENT REVIEW",
                "rating": 5.0,
                "timestamp": 3,
            },
        ]
        self.candidates = ["C1", "C2", "C3"]
        self.titles = {
            "C1": "Candidate One",
            "C2": "Candidate Two",
            "C3": "Candidate Three",
        }

    def test_prompt_uses_t_minus_2_history_and_t_minus_1_as_demonstration(self):
        messages = build_icl_messages(self.history, self.candidates, self.titles)
        prompt = messages[1]["content"]
        self.assertIn("Earlier purchase history through time step t-2", prompt)
        self.assertIn("1. Old Product One", prompt)
        self.assertIn("2. Old Product Two", prompt)
        self.assertNotIn("3. Demonstrated Recent Product", prompt)
        self.assertIn(
            "the item you should have recommended to me was: Demonstrated Recent Product",
            prompt,
        )
        self.assertIn("Now that I have bought Demonstrated Recent Product", prompt)

    def test_prompt_does_not_expose_reviews_ratings_or_asins(self):
        messages = build_icl_messages(self.history, self.candidates, self.titles)
        prompt = messages[1]["content"]
        for forbidden in (
            "SECRET REVIEW ONE",
            "SECRET REVIEW TWO",
            "SECRET RECENT REVIEW",
            "H1",
            "H2",
            "H3",
            "C1",
            "C2",
            "2.0",
            "4.0",
            "5.0",
        ):
            self.assertNotIn(forbidden, prompt)

    def test_prompt_uses_numbered_current_candidates(self):
        messages = build_icl_messages(self.history, self.candidates, self.titles)
        prompt = messages[1]["content"]
        self.assertIn("Candidate 1: Candidate One", prompt)
        self.assertIn("Candidate 2: Candidate Two", prompt)
        self.assertIn("Candidate 3: Candidate Three", prompt)
        self.assertIn("Use every integer from 1 through 3 exactly once", prompt)

    def test_shared_numbered_parser_maps_back_to_frozen_asins(self):
        ranking = parse_complete_ranking('{"ranking":[2,3,1]}', self.candidates)
        self.assertEqual(ranking, ["C2", "C3", "C1"])


if __name__ == "__main__":
    unittest.main()
