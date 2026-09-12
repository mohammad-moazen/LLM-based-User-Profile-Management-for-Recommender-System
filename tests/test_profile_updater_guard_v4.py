"""Regression tests for the Profile Updater v4 retention guard."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.pure import (
    UserProfile,
    apply_retention_guard,
    is_more_informative_overlap,
)


class ProfileUpdaterGuardV4Tests(unittest.TestCase):
    def test_directional_overlap_prefers_richer_sentence(self):
        short = "It has a lot of charm and it is challenging enough."
        long = "Beautiful game. It has a lot of charm and it is challenging enough."
        self.assertTrue(is_more_informative_overlap(long, short))
        self.assertFalse(is_more_informative_overlap(short, long))

    def test_guard_corrects_model_when_shorter_overlap_was_selected(self):
        short = "It has a lot of charm and it is challenging enough."
        long = "Beautiful game. It has a lot of charm and it is challenging enough."
        allowed = UserProfile(likes=(short, long))
        model_selected = UserProfile(likes=(short,))

        safe, restored, allowed_removals = apply_retention_guard(
            model_selected,
            allowed_profile=allowed,
        )

        self.assertEqual(safe.likes, (long,))
        self.assertEqual(restored["likes"], [long])
        self.assertEqual(allowed_removals["likes"], [short])

    def test_guard_preserves_unrelated_unique_omission(self):
        unique = "Arrived even faster than i expected."
        other = "It is so nostalgic and fun and awesome and hard...."
        allowed = UserProfile(likes=(unique, other))
        model_selected = UserProfile(likes=(other,))

        safe, restored, allowed_removals = apply_retention_guard(
            model_selected,
            allowed_profile=allowed,
        )

        self.assertEqual(safe.likes, (unique, other))
        self.assertEqual(restored["likes"], [unique])
        self.assertEqual(allowed_removals["likes"], [])


if __name__ == "__main__":
    unittest.main()
