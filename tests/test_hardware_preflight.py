"""Tests for Phase 10A hardware-saturation preflight helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis.hardware_preflight import (
    canonical_json_content,
    evaluate_concurrency_candidate,
)


class HardwarePreflightTests(unittest.TestCase):
    def test_canonical_json_ignores_object_key_order_and_whitespace(self):
        left = '{"ranking": [1, 2, 3], "meta": "x"}'
        right = '{ "meta" : "x", "ranking":[1,2,3] }'
        self.assertEqual(canonical_json_content(left), canonical_json_content(right))

    def test_two_worker_candidate_accepts_only_with_repeatability_speedup_and_vram_headroom(self):
        outputs = [
            '{"ranking":[1,2,3]}',
            '{"ranking":[3,2,1]}',
        ]
        result = evaluate_concurrency_candidate(
            sequential_outputs=outputs,
            concurrent_outputs=outputs,
            sequential_wall_seconds=20.0,
            concurrent_wall_seconds=12.0,
            min_throughput_speedup=1.15,
            peak_vram_used_mib=7000.0,
            vram_total_mib=8192.0,
            max_vram_fraction=0.97,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["recommended_max_concurrent_predictions"], 2)
        self.assertAlmostEqual(float(result["throughput_speedup"]), 20.0 / 12.0)

    def test_two_worker_candidate_rejects_output_mismatch(self):
        result = evaluate_concurrency_candidate(
            sequential_outputs=['{"ranking":[1,2,3]}'],
            concurrent_outputs=['{"ranking":[1,3,2]}'],
            sequential_wall_seconds=10.0,
            concurrent_wall_seconds=5.0,
            min_throughput_speedup=1.15,
            peak_vram_used_mib=6000.0,
            vram_total_mib=8192.0,
            max_vram_fraction=0.97,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("concurrent_outputs_not_exactly_repeatable", result["rejection_reasons"])

    def test_two_worker_candidate_rejects_insufficient_speedup(self):
        outputs = ['{"ranking":[1,2,3]}']
        result = evaluate_concurrency_candidate(
            sequential_outputs=outputs,
            concurrent_outputs=outputs,
            sequential_wall_seconds=10.0,
            concurrent_wall_seconds=9.5,
            min_throughput_speedup=1.15,
            peak_vram_used_mib=None,
            vram_total_mib=None,
            max_vram_fraction=0.97,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("throughput_speedup_below_threshold", result["rejection_reasons"])
        self.assertFalse(result["vram_check_available"])


if __name__ == "__main__":
    unittest.main()
