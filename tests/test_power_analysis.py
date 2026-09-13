"""Tests for Phase 8 prospective paired-user power planning helpers."""

from __future__ import annotations

import csv
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis.power_analysis import (
    NDCG_KS,
    load_phase7_per_user_csv,
    normal_approx_power,
    normal_approx_required_n,
    paired_user_deltas,
    round_up_with_margin,
    summarize_paired_effect,
)


class PowerAnalysisTests(unittest.TestCase):
    def test_required_n_matches_normal_approximation(self):
        # For d_z=0.5, alpha=.05 two-sided, 80% power, the standard normal
        # approximation is just over 31 users and therefore rounds up to 32.
        required = normal_approx_required_n(0.5, alpha=0.05, power=0.80, two_sided=True)
        self.assertEqual(required, 32)
        self.assertGreaterEqual(normal_approx_power(0.5, 32, alpha=0.05), 0.80)

    def test_margin_rounding_is_always_upward(self):
        self.assertEqual(
            round_up_with_margin(116, safety_margin_fraction=0.20, round_to=10),
            140,
        )

    def test_paired_effect_uses_user_level_differences(self):
        per_user = {
            "u1": {"PURE": {10: 0.6}, "Recency-Focused": {10: 0.4}},
            "u2": {"PURE": {10: 0.5}, "Recency-Focused": {10: 0.4}},
            "u3": {"PURE": {10: 0.4}, "Recency-Focused": {10: 0.4}},
        }
        deltas = paired_user_deltas(per_user, baseline="Recency-Focused", k=10)

        # Binary floating-point subtraction does not guarantee exact decimal
        # representations (for example, 0.6 - 0.4 may be stored as
        # 0.19999999999999996). The scientific requirement here is numerical
        # equality to the expected paired user-level deltas, not bitwise decimal
        # equality, so compare with unittest's floating-point-aware assertion.
        expected = [0.2, 0.1, 0.0]
        self.assertEqual(len(deltas), len(expected))
        for actual, wanted in zip(deltas, expected):
            self.assertAlmostEqual(actual, wanted)

        summary = summarize_paired_effect(deltas)
        self.assertAlmostEqual(float(summary["mean_delta"]), 0.1)
        self.assertAlmostEqual(float(summary["sd_delta"]), 0.1)
        self.assertAlmostEqual(float(summary["paired_effect_dz"]), 1.0)

    def test_phase7_csv_loader_requires_all_methods_and_cutoffs(self):
        prefixes = {
            "Sequential": "sequential",
            "Recency-Focused": "recency_focused",
            "ICL": "icl",
            "PURE": "pure",
        }
        fields = ["user_id"] + [
            f"{prefix}_ndcg_at_{k}"
            for prefix in prefixes.values()
            for k in NDCG_KS
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "per_user_ndcg.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                row = {"user_id": "u1"}
                for field in fields[1:]:
                    row[field] = "0.25"
                writer.writerow(row)

            loaded = load_phase7_per_user_csv(path)
            self.assertEqual(set(loaded), {"u1"})
            self.assertEqual(loaded["u1"]["PURE"][10], 0.25)
            self.assertEqual(loaded["u1"]["Recency-Focused"][20], 0.25)


if __name__ == "__main__":
    unittest.main()
