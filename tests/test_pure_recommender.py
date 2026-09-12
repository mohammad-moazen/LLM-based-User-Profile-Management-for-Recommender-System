"""Tests for PURE STEP 3 recommender prompt construction."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.pure import (
    PAPER_RECOMMENDER_INSTRUCTION,
    UserProfile,
    build_pure_recommender_messages,
    pure_recommender_response_format,
)


class PureRecommenderTests(unittest.TestCase):
    def setUp(self):
        self.history = [
            {"title": "Old Game"},
            {"title": "Recent Game"},
        ]
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

    def test_prompt_uses_history_profile_and_numbered_candidates(self):
        messages = build_pure_recommender_messages(
            history=self.history,
            profile=self.profile,
            candidate_asins=self.candidate_asins,
            item_titles=self.item_titles,
        )
        self.assertEqual(len(messages), 2)
        prompt = messages[1]["content"]
        self.assertIn("Old Game", prompt)
        self.assertIn("Recent Game", prompt)
        self.assertIn("Positive aspects:", prompt)
        self.assertIn("fun gameplay", prompt)
        self.assertIn("Negative aspects:", prompt)
        self.assertIn("bad controls", prompt)
        self.assertIn("Key Features:", prompt)
        self.assertIn("local multiplayer", prompt)
        self.assertIn("Candidate 1: Candidate Title 1", prompt)
        self.assertIn("Candidate 20: Candidate Title 20", prompt)
        self.assertNotIn("A01", prompt)
        self.assertIn("likelihood of being purchased", prompt)
        self.assertIn("ranking", prompt)

    def test_paper_instruction_constant_keeps_published_labels(self):
        self.assertIn("Positive aspects: {likes}", PAPER_RECOMMENDER_INSTRUCTION)
        self.assertIn("Negative aspects: {dislikes}", PAPER_RECOMMENDER_INSTRUCTION)
        self.assertIn("Key Features: {key_features}", PAPER_RECOMMENDER_INSTRUCTION)
        self.assertIn("from 1 to 20", PAPER_RECOMMENDER_INSTRUCTION)

    def test_schema_requires_complete_unique_twenty_item_ranking(self):
        response_format = pure_recommender_response_format(20)
        self.assertEqual(response_format["type"], "json_schema")
        schema = response_format["json_schema"]["schema"]
        ranking = schema["properties"]["ranking"]
        self.assertEqual(ranking["minItems"], 20)
        self.assertEqual(ranking["maxItems"], 20)
        self.assertTrue(ranking["uniqueItems"])
        self.assertEqual(ranking["items"]["enum"], list(range(1, 21)))
        self.assertEqual(schema["required"], ["ranking"])
        self.assertFalse(schema["additionalProperties"])

    def test_requires_twenty_candidates_for_paper_evaluation(self):
        with self.assertRaises(ValueError):
            build_pure_recommender_messages(
                history=self.history,
                profile=self.profile,
                candidate_asins=self.candidate_asins[:19],
                item_titles=self.item_titles,
            )


if __name__ == "__main__":
    unittest.main()
