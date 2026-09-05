import unittest

from pure_recommender.data.models import CanonicalInteraction
from pure_recommender.data.preprocessing import PreprocessingReport, summarize_histories


class PreprocessingSummaryTests(unittest.TestCase):
    def test_eligibility_uses_cleaned_history(self):
        rows = [
            CanonicalInteraction("u1", f"A{i}", f"T{i}", "r", 5.0, i, i)
            for i in range(4)
        ] + [
            CanonicalInteraction("u2", f"B{i}", f"T{i}", "r", 5.0, i, 100 + i)
            for i in range(3)
        ]
        report = PreprocessingReport()
        summarize_histories(rows, report, min_history=3)
        self.assertEqual(report.final_users, 2)
        self.assertEqual(report.eligible_users, 1)
        self.assertEqual(report.final_interactions, 7)


if __name__ == "__main__":
    unittest.main()
