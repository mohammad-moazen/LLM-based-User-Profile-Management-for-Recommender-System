"""Unit tests for deterministic Phase 7 analysis helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis.final_results import (
    bootstrap_paired_user_delta,
    compute_per_user_ndcg,
    compute_rank_summary,
    compute_win_tie_loss,
    relative_improvement_percent,
    write_grouped_ndcg_svg,
)


class FinalAnalysisTests(unittest.TestCase):
    def test_per_user_aggregation_preserves_equal_user_weighting(self):
        rows = [
            {"user_id": "u1", "target_rank": 1, "ndcg": {"1": 1.0, "5": 1.0, "10": 1.0, "20": 1.0}},
            {"user_id": "u1", "target_rank": 20, "ndcg": {"1": 0.0, "5": 0.0, "10": 0.0, "20": 0.2}},
            {"user_id": "u2", "target_rank": 2, "ndcg": {"1": 0.0, "5": 0.63, "10": 0.63, "20": 0.63}},
        ]
        per_user = compute_per_user_ndcg(rows)
        self.assertAlmostEqual(per_user["u1"][1], 0.5)
        self.assertAlmostEqual(per_user["u1"][20], 0.6)
        self.assertAlmostEqual(per_user["u2"][5], 0.63)

    def test_paired_bootstrap_is_deterministic_for_fixed_seed(self):
        pure = {
            "u1": {1: 0.8, 5: 0.8, 10: 0.8, 20: 0.8},
            "u2": {1: 0.6, 5: 0.6, 10: 0.6, 20: 0.6},
            "u3": {1: 0.4, 5: 0.4, 10: 0.4, 20: 0.4},
        }
        baseline = {
            "u1": {1: 0.5, 5: 0.5, 10: 0.5, 20: 0.5},
            "u2": {1: 0.5, 5: 0.5, 10: 0.5, 20: 0.5},
            "u3": {1: 0.5, 5: 0.5, 10: 0.5, 20: 0.5},
        }
        first = bootstrap_paired_user_delta(
            pure,
            baseline,
            k=10,
            repetitions=1000,
            seed=42,
            label="baseline",
        )
        second = bootstrap_paired_user_delta(
            pure,
            baseline,
            k=10,
            repetitions=1000,
            seed=42,
            label="baseline",
        )
        self.assertEqual(first, second)
        self.assertAlmostEqual(float(first["observed_mean_delta"]), 0.1)

    def test_win_tie_loss_and_relative_improvement(self):
        pure = {
            "u1": {1: 0.5, 5: 0.5, 10: 0.5, 20: 0.5},
            "u2": {1: 0.5, 5: 0.5, 10: 0.5, 20: 0.5},
            "u3": {1: 0.5, 5: 0.5, 10: 0.5, 20: 0.5},
        }
        baseline = {
            "u1": {1: 0.4, 5: 0.4, 10: 0.4, 20: 0.4},
            "u2": {1: 0.5, 5: 0.5, 10: 0.5, 20: 0.5},
            "u3": {1: 0.6, 5: 0.6, 10: 0.6, 20: 0.6},
        }
        self.assertEqual(
            compute_win_tie_loss(pure, baseline, k=5),
            {"wins": 1, "ties": 1, "losses": 1},
        )
        self.assertAlmostEqual(relative_improvement_percent(0.6, 0.5), 20.0)
        self.assertIsNone(relative_improvement_percent(0.1, 0.0))

    def test_rank_summary_and_svg_writer(self):
        rows = [
            {"target_rank": 1},
            {"target_rank": 5},
            {"target_rank": 10},
            {"target_rank": 20},
        ]
        summary = compute_rank_summary(rows)
        self.assertEqual(summary["sessions"], 4)
        self.assertAlmostEqual(float(summary["top5_rate"]), 0.5)
        self.assertAlmostEqual(float(summary["top10_rate"]), 0.75)

        scores = {
            "Sequential": {1: 0.1, 5: 0.2, 10: 0.3, 20: 0.4},
            "Recency-Focused": {1: 0.11, 5: 0.21, 10: 0.31, 20: 0.41},
            "ICL": {1: 0.09, 5: 0.19, 10: 0.29, 20: 0.39},
            "PURE": {1: 0.12, 5: 0.22, 10: 0.32, 20: 0.42},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chart.svg"
            write_grouped_ndcg_svg(path, scores)
            text = path.read_text(encoding="utf-8")
            self.assertIn("<svg", text)
            self.assertIn("PURE", text)
            self.assertIn("NDCG@10", text)


if __name__ == "__main__":
    unittest.main()
