from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.phase10_profile_canonical_v2 import (
    POLICY_NAME,
    canonicalize_exact_duplicate_ids,
    duplicate_count,
    parse_profile_update_v2,
)
from pure_recommender.pure import UserProfile, build_profile_id_map


class Phase10ProfileCanonicalV2Tests(unittest.TestCase):
    def setUp(self):
        self.allowed = UserProfile(
            likes=("responsive controls", "comfortable shape"),
            dislikes=("stiff cable", "noisy buttons"),
            key_features=("precise sensor", "light weight"),
        )
        self.id_map = build_profile_id_map(self.allowed)

    def test_policy_name(self):
        self.assertEqual(POLICY_NAME, "exact_duplicate_id_canonicalization_v2")

    def test_duplicate_id_collapses_to_same_profile(self):
        text = '{"likes":["L001","L002"],"dislikes":["D001","D002","D002"],"key_features":["K001","K002"]}'
        profile, removed = parse_profile_update_v2(
            text, allowed_profile=self.allowed, id_map=self.id_map
        )
        self.assertEqual(profile, self.allowed)
        self.assertEqual(removed["dislikes"], 1)
        self.assertEqual(duplicate_count(removed), 1)

    def test_first_occurrence_order_is_preserved(self):
        normalized, removed = canonicalize_exact_duplicate_ids(
            '{"likes":["L002","L001","L002"],"dislikes":[],"key_features":[]}',
            id_map=self.id_map,
        )
        self.assertEqual(normalized, '{"likes":["L002","L001"],"dislikes":[],"key_features":[]}')
        self.assertEqual(removed["likes"], 1)

    def test_unknown_id_raises(self):
        with self.assertRaises(ValueError):
            parse_profile_update_v2(
                '{"likes":["L999"],"dislikes":[],"key_features":[]}',
                allowed_profile=self.allowed,
                id_map=self.id_map,
            )

    def test_cross_category_id_raises(self):
        with self.assertRaises(ValueError):
            parse_profile_update_v2(
                '{"likes":["D001"],"dislikes":[],"key_features":[]}',
                allowed_profile=self.allowed,
                id_map=self.id_map,
            )

    def test_wrong_keys_raise(self):
        with self.assertRaises(ValueError):
            canonicalize_exact_duplicate_ids(
                '{"likes":[],"dislikes":[],"features":[]}', id_map=self.id_map
            )


if __name__ == "__main__":
    unittest.main()
