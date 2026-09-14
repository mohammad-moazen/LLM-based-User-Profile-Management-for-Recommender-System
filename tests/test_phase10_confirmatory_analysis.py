from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (SRC_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_phase10_confirmatory_analysis as analysis


class Phase10ConfirmatoryAnalysisTests(unittest.TestCase):
    def test_frozen_missing_output_policy_targets_only_known_session(self):
        self.assertEqual(analysis.EXPECTED_UNRESOLVED_SESSION, "A3C8IUK92R6137:13")
        self.assertEqual(analysis.EXPECTED_SESSIONS, 767)

    def test_student_t_cdf_is_symmetric_at_zero(self):
        self.assertAlmostEqual(analysis._student_t_cdf(0.0, 149), 0.5, places=12)
        positive = analysis._student_t_cdf(2.0, 149)
        negative = analysis._student_t_cdf(-2.0, 149)
        self.assertAlmostEqual(positive + negative, 1.0, places=12)

    def test_paired_test_zero_differences(self):
        result = analysis._paired_test([0.0] * 150)
        self.assertEqual(result["n_users"], 150)
        self.assertEqual(result["p_value_two_sided"], 1.0)
        self.assertFalse(result["reject_null"])

    def test_t_critical_matches_df149_reference(self):
        critical = analysis._t_critical_two_sided(0.05, 149)
        self.assertAlmostEqual(critical, 1.976, places=3)


if __name__ == "__main__":
    unittest.main()
