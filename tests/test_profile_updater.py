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
    apply_retention_guard,
    build_profile_id_map,
    build_profile_updater_messages,
    concatenate_profile_and_extraction,
    is_clear_lexical_overlap,
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

    def test_build_id_map_is_deterministic_and_category_scoped(self):
        combined = concatenate_profile_and_extraction(self.previous, self.incoming)
        id_map = build_profile_id_map(combined)
        self.assertEqual(id_map["likes"]["L001"], "responsive controls")
        self.assertEqual(id_map["likes"]["L003"], "comfortable shape")
        self.assertEqual(id_map["dislikes"]["D001"], "stiff cable")
        self.assertEqual(id_map["key_features"]["K003"], "light weight")

    def test_prompt_contains_paper_template_ids_and_retention_rules(self):
        messages, combined, id_map = build_profile_updater_messages(self.previous, self.incoming)
        prompt = messages[1]["content"]
        system_prompt = messages[0]["content"]
        self.assertIn(PAPER_UPDATER_INSTRUCTION, prompt)
        self.assertIn('"id": "L001"', prompt)
        self.assertIn("responsive controls", prompt)
        self.assertIn("Return only the IDs", prompt)
        self.assertIn("Retain every unique entry by default", prompt)
        self.assertIn("if uncertain, preserve both", prompt)
        self.assertIn("never rewrite profile text", system_prompt.lower())
        self.assertEqual(len(messages), 2)
        self.assertEqual(combined.likes[0], "responsive controls")
        self.assertEqual(id_map["likes"]["L001"], "responsive controls")

    def test_schema_has_three_required_id_arrays_with_enums(self):
        combined = concatenate_profile_and_extraction(self.previous, self.incoming)
        id_map = build_profile_id_map(combined)
        response_format = profile_updater_response_format(id_map)
        self.assertEqual(response_format["type"], "json_schema")
        schema = response_format["json_schema"]["schema"]
        self.assertEqual(set(schema["properties"]), {"likes", "dislikes", "key_features"})
        self.assertEqual(set(schema["required"]), {"likes", "dislikes", "key_features"})
        self.assertIn("L001", schema["properties"]["likes"]["items"]["enum"])
        self.assertIn("D001", schema["properties"]["dislikes"]["items"]["enum"])
        self.assertFalse(schema["additionalProperties"])

    def test_parser_maps_same_category_ids_to_exact_strings(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        id_map = build_profile_id_map(allowed)
        updated = parse_profile_update(
            '{"likes":["L001","L003"],'
            '"dislikes":["D002"],'
            '"key_features":["K001","K003"]}',
            allowed_profile=allowed,
            id_map=id_map,
        )
        self.assertEqual(
            updated.to_dict(),
            {
                "likes": ["responsive controls", "comfortable shape"],
                "dislikes": ["cable feels stiff"],
                "key_features": ["precise sensor", "light weight"],
            },
        )

    def test_parser_rejects_unknown_or_cross_category_id(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        id_map = build_profile_id_map(allowed)
        with self.assertRaises(ValueError):
            parse_profile_update(
                '{"likes":["K001"],"dislikes":[],"key_features":[]}',
                allowed_profile=allowed,
                id_map=id_map,
            )
        with self.assertRaises(ValueError):
            parse_profile_update(
                '{"likes":["L999"],"dislikes":[],"key_features":[]}',
                allowed_profile=allowed,
                id_map=id_map,
            )

    def test_parser_rejects_duplicate_id(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        id_map = build_profile_id_map(allowed)
        with self.assertRaises(ValueError):
            parse_profile_update(
                '{"likes":["L001","L001"],"dislikes":[],"key_features":[]}',
                allowed_profile=allowed,
                id_map=id_map,
            )

    def test_parser_rejects_wrong_keys(self):
        allowed = concatenate_profile_and_extraction(self.previous, self.incoming)
        id_map = build_profile_id_map(allowed)
        with self.assertRaises(ValueError):
            parse_profile_update(
                '{"likes":[],"dislikes":[],"features":[]}',
                allowed_profile=allowed,
                id_map=id_map,
            )

    def test_clear_overlap_detects_containment_but_not_unrelated_preferences(self):
        self.assertTrue(
            is_clear_lexical_overlap(
                "It has a lot of charm and it is challenging enough.",
                "Beautiful game. It has a lot of charm and it is challenging enough.",
            )
        )
        self.assertFalse(
            is_clear_lexical_overlap(
                "Arrived even faster than i expected.",
                "It is so nostalgic and fun and awesome and hard.",
            )
        )

    def test_retention_guard_restores_unique_omissions(self):
        allowed = UserProfile(
            likes=(
                "Arrived even faster than i expected.",
                "It is so nostalgic and fun and awesome and hard.",
            )
        )
        model_selected = UserProfile(likes=("It is so nostalgic and fun and awesome and hard.",))
        safe, restored, allowed_removals = apply_retention_guard(
            model_selected,
            allowed_profile=allowed,
        )
        self.assertEqual(safe.likes, allowed.likes)
        self.assertEqual(restored["likes"], ["Arrived even faster than i expected."])
        self.assertEqual(allowed_removals["likes"], [])

    def test_retention_guard_allows_clear_overlap_and_keeps_more_informative_selected_text(self):
        short = "It has a lot of charm and it is challenging enough."
        long = "Beautiful game. It has a lot of charm and it is challenging enough."
        allowed = UserProfile(likes=(short, long))
        model_selected = UserProfile(likes=(long,))
        safe, restored, allowed_removals = apply_retention_guard(
            model_selected,
            allowed_profile=allowed,
        )
        self.assertEqual(safe.likes, (long,))
        self.assertEqual(restored["likes"], [])
        self.assertEqual(allowed_removals["likes"], [short])

    def test_retention_guard_collapses_exact_duplicate_input(self):
        allowed = UserProfile(key_features=("precise sensor", "precise sensor"))
        model_selected = UserProfile(key_features=("precise sensor",))
        safe, restored, allowed_removals = apply_retention_guard(
            model_selected,
            allowed_profile=allowed,
        )
        self.assertEqual(safe.key_features, ("precise sensor",))
        self.assertEqual(restored["key_features"], [])
        self.assertEqual(allowed_removals["key_features"], [])


if __name__ == "__main__":
    unittest.main()
