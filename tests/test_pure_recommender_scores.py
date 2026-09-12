"""Tests for score-based PURE recommender serialization."""

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
    build_pure_recommender_score_messages,
    parse_candidate_scores,
    pure_recommender_score_response_format,
)


class PureRecommenderScoreTests(unittest.TestCase):
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

    def test_score_schema_requires_every_candidate_key(self):
        response_format = pure_recommender_score_response_format(20)
        schema = response_format["json_schema"]["schema"]
        scores = schema["properties"]["scores"]
        self.assertEqual(scores["required"], [str(i) for i in range(1, 21)])
        self.assertFalse(scores["additionalProperties"])
        self.assertEqual(set(scores["properties"]), {str(i) for i in range(1, 21)})
        self.assertEqual(scores["properties"]["1"]["minimum"], 0)
        self.assertEqual(scores["properties"]["1"]["maximum"], 1000)

    def test_score_prompt_keeps_history_profile_and_hides_asins(self):
        messages = build_pure_recommender_score_messages(
            history=self.history,
            profile=self.profile,
            candidate_asins=self.candidate_asins,
            item_titles=self.item_titles,
        )
        prompt = messages[1]["content"]
        self.assertIn("Old Game", prompt)
        self.assertIn("Recent Game", prompt)
        self.assertIn("Positive aspects:", prompt)
        self.assertIn("fun gameplay", prompt)
        self.assertIn("Candidate 20: Candidate Title 20", prompt)
        self.assertIn("purchase-likelihood score", prompt)
        self.assertIn("`scores`", prompt)
        self.assertNotIn("A01", prompt)

    def test_parser_derives_complete_ranking_and_breaks_ties_by_candidate_number(self):
        scores = {str(i): 1000 - i for i in range(1, 21)}
        scores["2"] = scores["1"]
        raw = json.dumps({"scores": scores})
        ranking, parsed_scores, tie_groups, tied_candidates = parse_candidate_scores(
            raw, self.candidate_asins
        )
        self.assertEqual(len(ranking), 20)
        self.assertEqual(set(ranking), set(self.candidate_asins))
        self.assertEqual(ranking[0], "A01")
        self.assertEqual(ranking[1], "A02")
        self.assertEqual(parsed_scores[1], parsed_scores[2])
        self.assertEqual(tie_groups, 1)
        self.assertEqual(tied_candidates, 2)

    def test_parser_rejects_missing_candidate_score(self):
        scores = {str(i): i for i in range(1, 20)}
        with self.assertRaises(ValueError):
            parse_candidate_scores(json.dumps({"scores": scores}), self.candidate_asins)

    def test_parser_rejects_non_integer_score(self):
        scores = {str(i): i for i in range(1, 21)}
        scores["7"] = 7.5
        with self.assertRaises(ValueError):
            parse_candidate_scores(json.dumps({"scores": scores}), self.candidate_asins)


if __name__ == "__main__":
    unittest.main()
