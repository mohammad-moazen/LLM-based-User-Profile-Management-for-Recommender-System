"""Tests for the PURE Review Extractor component."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.pure import (
    build_review_extractor_messages,
    parse_review_extraction,
    review_extractor_response_format,
)


class ReviewExtractorTests(unittest.TestCase):
    def setUp(self):
        self.interaction = {
            "user_id": "u1",
            "asin": "B000TEST01",
            "title": "RGB Wired Example Gaming Mouse",
            "review_text": "I love the light weight and precise sensor, but the cable feels stiff.",
            "rating": 4.0,
            "timestamp": 123456789,
        }

    def test_prompt_contains_paper_relevant_review_context_and_strict_grounding_rules(self):
        messages = build_review_extractor_messages(self.interaction)
        prompt = messages[1]["content"]
        system_prompt = messages[0]["content"]
        self.assertIn("B000TEST01", prompt)
        self.assertIn("RGB Wired Example Gaming Mouse", prompt)
        self.assertIn("Rating: 4", prompt)
        self.assertIn("light weight and precise sensor", prompt)
        self.assertIn("likes/dislikes/key features", prompt)
        self.assertIn("REVIEW TEXT between the markers is the only evidence source", prompt)
        self.assertIn("VERBATIM QUOTE", prompt)
        self.assertIn("Never copy a feature merely because it appears in the product name", prompt)
        self.assertIn("Never invent a preference from the numeric rating", prompt)
        self.assertIn("NEVER evidence", system_prompt)
        self.assertIn("verbatim quote", system_prompt)
        self.assertNotIn("123456789", prompt)
        self.assertNotIn("u1", prompt)

    def test_response_format_uses_three_required_arrays(self):
        response_format = review_extractor_response_format()
        self.assertEqual(response_format["type"], "json_schema")
        schema = response_format["json_schema"]["schema"]
        self.assertEqual(
            set(schema["properties"]),
            {"likes", "dislikes", "key_features"},
        )
        self.assertEqual(
            set(schema["required"]),
            {"likes", "dislikes", "key_features"},
        )
        self.assertFalse(schema["additionalProperties"])

    def test_parser_accepts_complete_structured_output(self):
        extraction = parse_review_extraction(
            '{"likes":["light weight"],'
            '"dislikes":["cable feels stiff"],'
            '"key_features":["precise sensor"]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(extraction.likes, ("light weight",))
        self.assertEqual(extraction.dislikes, ("cable feels stiff",))
        self.assertEqual(extraction.key_features, ("precise sensor",))

    def test_grounding_validation_is_case_and_whitespace_tolerant(self):
        extraction = parse_review_extraction(
            '{"likes":["LIGHT   WEIGHT"],"dislikes":[],"key_features":[]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(extraction.likes, ("LIGHT   WEIGHT",))

    def test_parser_rejects_title_only_feature_when_source_review_is_supplied(self):
        with self.assertRaisesRegex(ValueError, "non-verbatim or non-review-grounded"):
            parse_review_extraction(
                '{"likes":[],"dislikes":[],"key_features":["RGB Wired"]}',
                source_review=self.interaction["review_text"],
            )

    def test_parser_rejects_paraphrase_when_source_review_is_supplied(self):
        with self.assertRaisesRegex(ValueError, "non-verbatim or non-review-grounded"):
            parse_review_extraction(
                '{"likes":["lightweight mouse"],"dislikes":[],"key_features":[]}',
                source_review=self.interaction["review_text"],
            )

    def test_parser_preserves_duplicate_entries_for_later_updater(self):
        extraction = parse_review_extraction(
            '{"likes":["precise sensor","precise sensor"],'
            '"dislikes":[],"key_features":[]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(
            extraction.likes,
            ("precise sensor", "precise sensor"),
        )

    def test_parser_rejects_wrong_keys_without_repair(self):
        with self.assertRaises(ValueError):
            parse_review_extraction(
                '{"likes":[],"dislikes":[],"features":[]}'
            )

    def test_parser_rejects_non_string_or_blank_entries(self):
        with self.assertRaises(ValueError):
            parse_review_extraction(
                '{"likes":[1],"dislikes":[],"key_features":[]}'
            )
        with self.assertRaises(ValueError):
            parse_review_extraction(
                '{"likes":["   "],"dislikes":[],"key_features":[]}'
            )


if __name__ == "__main__":
    unittest.main()
