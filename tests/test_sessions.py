import unittest

from pure_recommender.data.models import CanonicalInteraction
from pure_recommender.data.sessions import (
    build_recommendation_sessions,
    group_histories,
    select_eligible_users,
    validate_sessions,
)


def interaction(user, asin, timestamp, source_index):
    return CanonicalInteraction(
        user_id=user,
        asin=asin,
        title=f"Title {asin}",
        review_text=f"Review {asin}",
        rating=5.0,
        timestamp=timestamp,
        source_row_index=source_index,
    )


class SessionTests(unittest.TestCase):
    def setUp(self):
        rows = [
            interaction("u1", "A", 10, 0),
            interaction("u1", "B", 20, 1),
            interaction("u1", "C", 30, 2),
            interaction("u1", "D", 40, 3),
            interaction("u1", "E", 50, 4),
        ]
        self.histories = group_histories(rows)
        self.universe = list("ABCDEFGHIJKLMNOQRSTUVWXYZ")

    def test_first_target_is_fourth_interaction(self):
        sessions = build_recommendation_sessions(
            self.histories, self.universe, ["u1"], min_history=3, candidate_size=20, candidate_seed=42
        )
        self.assertEqual(sessions[0].target_asin, "D")
        self.assertEqual(sessions[0].target_position, 4)

    def test_negatives_never_include_any_user_item(self):
        sessions = build_recommendation_sessions(
            self.histories, self.universe, ["u1"], min_history=3, candidate_size=20, candidate_seed=42
        )
        validate_sessions(sessions, self.histories, candidate_size=20)

    def test_candidate_generation_is_deterministic(self):
        a = build_recommendation_sessions(
            self.histories, self.universe, ["u1"], min_history=3, candidate_size=20, candidate_seed=42
        )
        b = build_recommendation_sessions(
            self.histories, self.universe, ["u1"], min_history=3, candidate_size=20, candidate_seed=42
        )
        self.assertEqual(a, b)

    def test_user_selection_is_deterministic(self):
        histories = {
            "u1": self.histories["u1"],
            "u2": self.histories["u1"],
            "u3": self.histories["u1"],
        }
        first = select_eligible_users(histories, min_history=3, max_users=2, selection_seed=7)
        second = select_eligible_users(histories, min_history=3, max_users=2, selection_seed=7)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
