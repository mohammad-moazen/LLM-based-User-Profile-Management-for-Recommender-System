import math
import unittest

from pure_recommender.evaluation.metrics import aggregate_user_ndcg, ndcg_at_k_from_rank


class NDCGTests(unittest.TestCase):
    def test_rank_one_is_perfect(self):
        self.assertEqual(ndcg_at_k_from_rank(1, 20), 1.0)

    def test_rank_beyond_cutoff_is_zero(self):
        self.assertEqual(ndcg_at_k_from_rank(6, 5), 0.0)

    def test_rank_two_discount(self):
        self.assertAlmostEqual(ndcg_at_k_from_rank(2, 20), 1.0 / math.log2(3))

    def test_user_level_aggregation(self):
        result = aggregate_user_ndcg({"A": [1, 2], "B": [2]}, ks=(20,))
        a = (1.0 + 1.0 / math.log2(3)) / 2.0
        b = 1.0 / math.log2(3)
        self.assertAlmostEqual(result[20], (a + b) / 2.0)


if __name__ == "__main__":
    unittest.main()
