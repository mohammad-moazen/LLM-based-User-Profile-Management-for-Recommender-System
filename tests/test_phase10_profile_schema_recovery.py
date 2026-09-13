from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.phase10_profile_schema_recovery import hardened_profile_updater_response_format
from pure_recommender.pure import UserProfile, build_profile_id_map


class SchemaRecoveryTests(unittest.TestCase):
    def test_hardened_schema_requires_unique_ids(self):
        profile = UserProfile(likes=("a", "b"), dislikes=("c",), key_features=("d",))
        response_format = hardened_profile_updater_response_format(build_profile_id_map(profile))
        props = response_format["json_schema"]["schema"]["properties"]
        self.assertTrue(props["likes"]["uniqueItems"])
        self.assertTrue(props["dislikes"]["uniqueItems"])
        self.assertTrue(props["key_features"]["uniqueItems"])
        self.assertEqual(props["likes"]["items"]["enum"], ["L001", "L002"])


if __name__ == "__main__":
    unittest.main()
