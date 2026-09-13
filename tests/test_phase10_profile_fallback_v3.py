from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.phase10_profile_fallback_v3 import (
    FALLBACK_POLICY,
    conservative_fallback_profile,
    is_context_overflow_error,
)
from pure_recommender.pure import UserProfile


class Phase10ProfileFallbackV3Tests(unittest.TestCase):
    def test_context_overflow_detection(self):
        self.assertTrue(
            is_context_overflow_error(
                "request (8277 tokens) exceeds the available context size (8192 tokens)"
            )
        )
        self.assertTrue(is_context_overflow_error("exceed_context_size_error"))
        self.assertFalse(is_context_overflow_error("temporary connection error"))

    def test_fallback_preserves_unique_evidence(self):
        profile = UserProfile(
            likes=("responsive controls", "comfortable shape"),
            dislikes=("stiff cable",),
            key_features=("precise sensor",),
        )
        updated, restored, removed = conservative_fallback_profile(profile)
        self.assertEqual(updated, profile)
        self.assertEqual(restored, {"likes": [], "dislikes": [], "key_features": []})
        self.assertEqual(removed, {"likes": [], "dislikes": [], "key_features": []})

    def test_fallback_still_allows_only_guard_v4_dominated_overlap_compaction(self):
        short = "It has a lot of charm and it is challenging enough."
        long = "Beautiful game. It has a lot of charm and it is challenging enough."
        profile = UserProfile(likes=(short, long))
        updated, _restored, removed = conservative_fallback_profile(profile)
        self.assertEqual(updated.likes, (long,))
        self.assertEqual(removed["likes"], [short])
        self.assertEqual(FALLBACK_POLICY, "preserve_all_then_guard_v4")


if __name__ == "__main__":
    unittest.main()
