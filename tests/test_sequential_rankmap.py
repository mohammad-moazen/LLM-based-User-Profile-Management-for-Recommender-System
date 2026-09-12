"""Tests for the Sequential rank-map fallback serialization."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.baselines.sequential import SYSTEM_PROMPT
from pure_recommender.baselines.sequential_rankmap import build_sequential_rankmap_messages
from pure_recommender.pure import parse_candidate_rankmap, pure_recommender_rankmap_response_format


class SequentialRankMapTests(unittest.TestCase):
    def setUp(self):
        self.history = [
            {"title": "First Purchase"},
            {"title": "Second Purchase"},
            {"title": "Most Recent Purchase"},
        ]
        self.candidate_asins = [f"A{i:02d}" for i in range(1, 21)]
        self.item_titles = {
            asin: f"Candidate Title {index}"
            for index, asin in enumerate(self.candidate_asins, start=1)
        }

    def test_fallback_preserves_sequential_visible_information(self):
        messages = build_sequential_rankmap_messages(
            history=self.history,
            candidate_asins=self.candidate_asins,
            item_titles=self.item_titles,
        )
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], SYSTEM_PROMPT)

        prompt = messages[1]["content"]
        self.assertIn("First Purchase", prompt)
        self.assertIn("Most Recent Purchase", prompt)
        self.assertIn("Candidate 1: Candidate Title 1", prompt)
        self.assertIn("Candidate 20: Candidate Title 20", prompt)
        self.assertIn("UNIQUE rank", prompt)
        self.assertIn("`ranks`", prompt)
        self.assertNotIn("A01", prompt)
        self.assertNotIn("rating", prompt.lower())
        self.assertNotIn("review", prompt.lower())
        self.assertNotIn("profile", prompt.lower())

    def test_rankmap_schema_requires_all_twenty_candidate_keys(self):
        response_format = pure_recommender_rankmap_response_format(20)
        schema = response_format["json_schema"]["schema"]
        ranks = schema["properties"]["ranks"]
        self.assertEqual(ranks["required"], [str(index) for index in range(1, 21)])
        self.assertFalse(ranks["additionalProperties"])

    def test_rankmap_parser_accepts_exact_permutation(self):
        payload = '{"ranks":{' + ",".join(
            f'"{index}":{index}' for index in range(1, 21)
        ) + "}}"
        ranking, rank_map = parse_candidate_rankmap(payload, self.candidate_asins)
        self.assertEqual(ranking, self.candidate_asins)
        self.assertEqual(rank_map[1], 1)
        self.assertEqual(rank_map[20], 20)

    def test_rankmap_parser_rejects_duplicate_rank(self):
        values = list(range(1, 21))
        values[-1] = 19
        payload = '{"ranks":{' + ",".join(
            f'"{index}":{value}' for index, value in enumerate(values, start=1)
        ) + "}}"
        with self.assertRaises(ValueError):
            parse_candidate_rankmap(payload, self.candidate_asins)


if __name__ == "__main__":
    unittest.main()
