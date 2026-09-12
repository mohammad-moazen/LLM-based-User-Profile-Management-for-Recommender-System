"""Tests for the PURE Profile Updater component."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.pure import (
    PAPER_UPDATER_INSTRUCTION,
    UserProfile,
    build_profile_updater_messages,
    concatenate_profile_and_extraction,
    parse_profile_update,
    profile_updater_response_format,
)


class ProfileUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.previous = UserProfile(
            likes=("responsive controls",),
            dislikes=("stiff cable",),
            key_features=("precise sensor",),
        )
        self.incoming = {
            "likes": ["responsive controls", "comfortable shape"],
            "dislikes": ["cable feels stiff"],
            "key_features": ["precise sensor", "light weight"],
        }

    def test_concatenate_matches_algorithm_order(self):
        combined = concatenate_profile_and_extraction(self.previous, self.incoming)
        self.assertEqual(
            combined.likes,
            ("responsive controls", "responsive controls", "comfortable shape"),
        )
        self.assertEqual(combined.dislikes, ("stiff cable", "cable feels stiff"))
        self.assertEqual(
            combined.key_features,
            ("precise sensor", "precise sensor", "light weight"),
        )

    def test_prompt_contains_paper_template_and_subset_rules(self):
        messages, combined = build_profile_updater_messages(self.previous, self.incoming)
        prompt = messages[1]["content"]
        self.assertIn(PAPER_UPDATER_INSTRUCTION, prompt)
        self.assertIn("responsive controls", prompt)
        self.assertIn("Do not paraphrase", prompt)
        self.assertIn("Do not move strings", prompt)
        self.assertEqual(len(messages), 2)
        self.assertEqual(combined.likes[0], "responsive controls")

    def test_schema_has_three_required_arrays(self):
        response_format = profile_updater_response_format()
        self.assertEqual(response_format["type"], "json_schema")
        schema = response_format["json_schema"]["schema"]
        self.assertEqual(set(schema["properties"]), {"likes", "dislikes", "key_features"})
        self.assertEqual(set(schema["required"]), {"likes", "dislikes", "key_features"})
        self.assertFalse(schema["additionalProperties"])

    def test_parser_accepts_exact_subset(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        updated = parse_profile_update(
            '{"likes":["responsive controls","comfortable shape"],'
            '"dislikes":["cable feels stiff"],'
            '"key_features":["precise sensor","light weight"]}',
            allowed_profile=allowed,
        )
        self.assertEqual(
            updated.to_dict(),
            {
                "likes": ["responsive controls", "comfortable shape"],
                "dislikes": ["cable feels stiff"],
                "key_features": ["precise sensor", "light weight"],
            },
        )

    def test_parser_rejects_new_paraphrased_text(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        with self.assertRaises(ValueError):
            parse_profile_update(
                '{"likes":["very responsive controls"],'
                '"dislikes":[],"key_features":[]}',
                allowed_profile=allowed,
            )

    def test_parser_rejects_cross_category_move(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        with self.assertRaises(ValueError):
            parse_profile_update(
                '{"likes":["precise sensor"],"dislikes":[],"key_features":[]}',
                allowed_profile=allowed,
            )

    def test_parser_rejects_duplicate_output(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        with self.assertRaises(ValueError):
            parse_profile_update(
                '{"likes":["responsive controls","responsive controls"],'
                '"dislikes":[],"key_features":[]}',
                allowed_profile=allowed,
            )

    def test_parser_rejects_wrong_keys(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        with self.assertRaises(ValueError):
            parse_profile_update(
                '{"likes":[],"dislikes":[],"features":[]}',
                allowed_profile=allowed,
            )


if __name__ == "__main__":
    unittest.main()
