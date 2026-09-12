"""Tests for PURE rank-map output serialization."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.pure import (
    UserProfile,
    build_pure_recommender_rankmap_messages,
    parse_candidate_rankmap,
    pure_recommender_rankmap_response_format,
)


class PureRecommenderRankMapTests(unittest.TestCase):
    def setUp(self):
        self.history = [{"title": "Old Game"}, {"title": "Recent Game"}]
        self.candidate_asins = [f"A{i:02d}" for i in range(1, 21)]
        self.item_titles = {
            asin: f"Candidate Title {index}"
            for index, asin in enumerate(self.candidate_asins, start=1)
        }
        self.profile = UserProfile(
            likes=("fun gameplay",),
            dislikes=("bad controls",),
            key_features=("local multiplayer",),
        )

    def test_schema_requires_every_candidate_key(self):
        response_format = pure_recommender_rankmap_response_format(20)
        schema = response_format["json_schema"]["schema"]
        ranks = schema["properties"]["ranks"]
        self.assertEqual(set(ranks["required"]), {str(i) for i in range(1, 21)})
        self.assertFalse(ranks["additionalProperties"])
        self.assertEqual(ranks["properties"]["1"]["minimum"], 1)
        self.assertEqual(ranks["properties"]["1"]["maximum"], 20)

    def test_prompt_requests_unique_rank_positions(self):
        messages = build_pure_recommender_rankmap_messages(
            history=self.history,
            profile=self.profile,
            candidate_asins=self.candidate_asins,
            item_titles=self.item_titles,
        )
        prompt = messages[1]["content"]
        self.assertIn("UNIQUE rank", prompt)
        self.assertIn("Use every rank value exactly once", prompt)
        self.assertIn("Candidate 20: Candidate Title 20", prompt)
        self.assertNotIn("A01", prompt)

    def test_parser_accepts_complete_rank_permutation(self):
        payload = {"ranks": {str(i): 21 - i for i in range(1, 21)}}
        ranking, ranks = parse_candidate_rankmap(json.dumps(payload), self.candidate_asins)
        self.assertEqual(ranks[20], 1)
        self.assertEqual(ranking[0], "A20")
        self.assertEqual(ranking[-1], "A01")

    def test_parser_rejects_duplicate_rank_values(self):
        values = {str(i): i for i in range(1, 21)}
        values[20] = 19
        with self.assertRaisesRegex(ValueError, "complete permutation"):
            parse_candidate_rankmap(json.dumps({"ranks": values}), self.candidate_asins)

    def test_parser_rejects_missing_candidate_key(self):
        values = {str(i): i for i in range(1, 20)}
        with self.assertRaisesRegex(ValueError, "keys mismatch"):
            parse_candidate_rankmap(json.dumps({"ranks": values}), self.candidate_asins)


if __name__ == "__main__":
    unittest.main()
