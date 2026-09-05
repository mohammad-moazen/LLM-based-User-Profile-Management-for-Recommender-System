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

    def test_prompt_uses_purchase_titles_but_not_reviews_ratings_or_history_asins(self):
        messages = build_sequential_messages(self.history, self.candidates, self.titles)
        prompt = messages[1]["content"]
        self.assertLess(prompt.index("First Product"), prompt.index("Second Product"))
        self.assertNotIn("H1", prompt)
        self.assertNotIn("H2", prompt)
        self.assertNotIn("SECRET REVIEW TEXT", prompt)
        self.assertNotIn("ANOTHER SECRET REVIEW", prompt)
        self.assertNotIn("1.0", prompt)
        self.assertNotIn("5.0", prompt)

    def test_prompt_numbers_candidates_without_exposing_candidate_asins(self):
        messages = build_sequential_messages(self.history, self.candidates, self.titles)
        prompt = messages[1]["content"]
        self.assertIn("Candidate 1: Candidate One", prompt)
        self.assertIn("Candidate 2: Candidate Two", prompt)
        self.assertIn("Candidate 3: Candidate Three", prompt)
        self.assertNotIn("C1", prompt)
        self.assertNotIn("C2", prompt)
        self.assertNotIn("C3", prompt)
        self.assertIn("every integer from 1 through 3 exactly once", prompt)
        self.assertIn("Do not return product names, ASINs, purchase-history numbers", prompt)

    def test_complete_integer_ranking_is_mapped_back_to_asins(self):
        ranking = parse_complete_ranking(
            '{"ranking":[2,1,3]}',
            self.candidates,
        )
        self.assertEqual(ranking, ["C2", "C1", "C3"])
        self.assertEqual(target_rank(ranking, "C1"), 2)

    def test_digit_strings_are_accepted_as_serialization_tolerance(self):
        ranking = parse_complete_ranking(
            '{"ranking":["3","1","2"]}',
            self.candidates,
        )
        self.assertEqual(ranking, ["C3", "C1", "C2"])

    def test_markdown_fenced_json_is_accepted(self):
        ranking = parse_complete_ranking(
            '```json\n{"ranking":[1,2,3]}\n```',
            self.candidates,
        )
        self.assertEqual(ranking, self.candidates)

    def test_duplicate_or_incomplete_ranking_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_complete_ranking('{"ranking":[1,1,3]}', self.candidates)
        with self.assertRaises(ValueError):
            parse_complete_ranking('{"ranking":[1,2]}', self.candidates)

    def test_out_of_range_candidate_number_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_complete_ranking('{"ranking":[1,2,4]}', self.candidates)

    def test_product_or_asin_strings_are_not_silently_repaired(self):
        with self.assertRaises(ValueError):
            parse_complete_ranking('{"ranking":["C1","C2","C3"]}', self.candidates)


if __name__ == "__main__":
    unittest.main()
