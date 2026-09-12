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

    def test_prompt_contains_review_context_and_evidence_rules(self):
        messages = build_review_extractor_messages(self.interaction)
        prompt = messages[1]["content"]
        system_prompt = messages[0]["content"]
        self.assertIn("B000TEST01", prompt)
        self.assertIn("RGB Wired Example Gaming Mouse", prompt)
        self.assertIn("Rating: 4", prompt)
        self.assertIn("light weight and precise sensor", prompt)
        self.assertIn("likes/dislikes/key features", prompt)
        self.assertIn("REVIEW TEXT between the markers is the only evidence source", prompt)
        self.assertIn("value may be a concise paraphrase", prompt)
        self.assertIn("evidence MUST be a short contiguous VERBATIM quote", prompt)
        self.assertIn("never use a title-only attribute as evidence", prompt)
        self.assertIn("never independent evidence", system_prompt)
        self.assertNotIn("123456789", prompt)
        self.assertNotIn("u1", prompt)

    def test_response_format_uses_three_required_evidence_arrays(self):
        response_format = review_extractor_response_format()
        self.assertEqual(response_format["type"], "json_schema")
        schema = response_format["json_schema"]["schema"]
        self.assertEqual(set(schema["properties"]), {"likes", "dislikes", "key_features"})
        self.assertEqual(set(schema["required"]), {"likes", "dislikes", "key_features"})
        item_schema = schema["properties"]["likes"]["items"]
        self.assertEqual(set(item_schema["properties"]), {"value", "evidence"})
        self.assertEqual(set(item_schema["required"]), {"value", "evidence"})
        self.assertFalse(item_schema["additionalProperties"])
        self.assertFalse(schema["additionalProperties"])

    def test_parser_accepts_paraphrase_with_verbatim_evidence(self):
        extraction = parse_review_extraction(
            '{"likes":[{"value":"lightweight mouse","evidence":"light weight"}],'
            '"dislikes":[{"value":"stiff cable","evidence":"cable feels stiff"}],'
            '"key_features":[{"value":"precise sensor","evidence":"precise sensor"}]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(extraction.to_profile_dict()["likes"], ["light weight"])
        self.assertEqual(extraction.to_profile_dict()["dislikes"], ["cable feels stiff"])
        self.assertEqual(extraction.to_profile_dict()["key_features"], ["precise sensor"])
        self.assertEqual(extraction.rejected_entries, ())
        self.assertEqual(
            extraction.to_audit_dict()["likes"][0],
            {"value": "lightweight mouse", "evidence": "light weight"},
        )

    def test_evidence_validation_is_case_and_whitespace_tolerant(self):
        extraction = parse_review_extraction(
            '{"likes":[{"value":"lightweight","evidence":"LIGHT   WEIGHT"}],'
            '"dislikes":[],"key_features":[]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(extraction.to_profile_dict()["likes"], ["LIGHT   WEIGHT"])
        self.assertEqual(extraction.rejected_entries, ())

    def test_title_only_nonreview_evidence_is_filtered_not_repaired(self):
        extraction = parse_review_extraction(
            '{"likes":[],"dislikes":[],"key_features":['
            '{"value":"RGB wired","evidence":"RGB Wired"}]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(extraction.to_profile_dict()["key_features"], [])
        self.assertEqual(len(extraction.rejected_entries), 1)
        rejected = extraction.rejected_entries[0]
        self.assertEqual(rejected.field, "key_features")
        self.assertEqual(rejected.value, "RGB wired")
        self.assertEqual(rejected.evidence, "RGB Wired")
        self.assertEqual(rejected.reason, "evidence_not_contiguous_span_of_review")

    def test_valid_and_invalid_entries_are_partitioned_independently(self):
        extraction = parse_review_extraction(
            '{"likes":[{"value":"lightweight","evidence":"light weight"}],'
            '"dislikes":[],"key_features":['
            '{"value":"precise sensing","evidence":"precise sensor"},'
            '{"value":"RGB","evidence":"RGB Wired"}]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(extraction.to_profile_dict()["likes"], ["light weight"])
        self.assertEqual(extraction.to_profile_dict()["key_features"], ["precise sensor"])
        self.assertEqual(len(extraction.rejected_entries), 1)
        self.assertEqual(extraction.rejected_entries[0].value, "RGB")

    def test_parser_accepts_normalized_value_when_evidence_is_grounded(self):
        extraction = parse_review_extraction(
            '{"likes":[{"value":"precise sensing","evidence":"precise sensor"}],'
            '"dislikes":[],"key_features":[]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(extraction.to_profile_dict()["likes"], ["precise sensor"])

    def test_parser_preserves_duplicate_evidence_for_later_updater(self):
        extraction = parse_review_extraction(
            '{"likes":['
            '{"value":"precise sensor","evidence":"precise sensor"},'
            '{"value":"accurate sensor","evidence":"precise sensor"}],'
            '"dislikes":[],"key_features":[]}',
            source_review=self.interaction["review_text"],
        )
        self.assertEqual(
            extraction.to_profile_dict()["likes"],
            ["precise sensor", "precise sensor"],
        )

    def test_parser_rejects_wrong_keys_without_repair(self):
        with self.assertRaises(ValueError):
            parse_review_extraction(
                '{"likes":[],"dislikes":[],"features":[]}'
            )

    def test_parser_rejects_malformed_entry_objects(self):
        with self.assertRaises(ValueError):
            parse_review_extraction(
                '{"likes":[{"value":"x"}],"dislikes":[],"key_features":[]}'
            )
        with self.assertRaises(ValueError):
            parse_review_extraction(
                '{"likes":[{"value":"x","evidence":"   "}],'
                '"dislikes":[],"key_features":[]}'
            )


if __name__ == "__main__":
    unittest.main()
