from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (SRC_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pure_recommender.phase10_analysis_contract import (
    PRIMARY_ALPHA,
    PRIMARY_METHOD_A,
    PRIMARY_METHOD_B,
    PRIMARY_METRIC,
    PRIMARY_TEST,
    PRIMARY_UNIT,
    PRIMARY_USERS,
)
from pure_recommender.phase5 import load_phase5_config
import run_phase10_confirmatory_pure_safe as runner


class Phase10ConfirmatoryPureContractTests(unittest.TestCase):
    def test_primary_analysis_contract_is_frozen(self):
        self.assertEqual(PRIMARY_METHOD_A, "PURE")
        self.assertEqual(PRIMARY_METHOD_B, "Recency-Focused")
        self.assertEqual(PRIMARY_METRIC, "NDCG@10")
        self.assertEqual(PRIMARY_UNIT, "user")
        self.assertEqual(PRIMARY_TEST, "paired_two_sided_t")
        self.assertEqual(PRIMARY_ALPHA, 0.05)
        self.assertEqual(PRIMARY_USERS, 150)

    def test_confirmatory_pure_config(self):
        config = load_phase5_config(REPO_ROOT / "config/phase10_confirmatory_pure.toml")
        self.assertEqual(config.experiment.max_sessions, 0)
        # Operational continuation after the first structural fallback failure is
        # deliberately non-fail-fast so the remaining frozen sessions can run.
        # This changes only execution control; prompt, parser, candidates,
        # generation settings, and scoring remain frozen.
        self.assertFalse(config.experiment.fail_fast)
        self.assertEqual(config.generation.temperature, 0.0)
        self.assertEqual(config.generation.max_tokens, 512)
        self.assertEqual(config.generation.seed, 42)
        self.assertTrue(str(config.input.sessions_path).endswith("outputs/phase9_confirmatory_cohort_v1/sessions.jsonl.gz"))
        self.assertTrue(str(config.input.profile_states_path).endswith("outputs/phase10_confirmatory_profile_updater_v2/profile_states.jsonl"))

    def test_resume_loader_rejects_mixed_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text(
                json.dumps({"run_version": "wrong", "session_id": "u:4", "status": "ok"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                runner._load_latest_results(path)


if __name__ == "__main__":
    unittest.main()
