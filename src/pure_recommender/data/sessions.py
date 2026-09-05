"""Deterministic construction of continuous sequential recommendation sessions."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import random
from typing import Iterable

from .models import CanonicalInteraction, RecommendationSession


def group_histories(
    interactions: Iterable[CanonicalInteraction],
) -> dict[str, list[CanonicalInteraction]]:
    histories: dict[str, list[CanonicalInteraction]] = defaultdict(list)
    for interaction in interactions:
        histories[interaction.user_id].append(interaction)
    for history in histories.values():
        history.sort(key=lambda row: (row.timestamp, row.source_row_index, row.asin))
    return dict(histories)


def _stable_int_seed(*parts: object) -> int:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], byteorder="big", signed=False)


def select_eligible_users(
    histories: dict[str, list[CanonicalInteraction]],
    min_history: int,
    max_users: int,
    selection_seed: int,
) -> list[str]:
    eligible = [user_id for user_id, history in histories.items() if len(history) >= min_history + 1]
    eligible.sort(key=lambda user_id: (_stable_int_seed(selection_seed, user_id), user_id))
    return eligible if max_users == 0 else eligible[:max_users]


def build_recommendation_sessions(
    histories: dict[str, list[CanonicalInteraction]],
    item_universe: Iterable[str],
    selected_users: Iterable[str],
    min_history: int,
    candidate_size: int,
    candidate_seed: int,
) -> list[RecommendationSession]:
    """Build every eligible next-item session for the selected users.

    Each session has one ground-truth target plus randomly sampled items that the
    user never interacts with anywhere in the cleaned full history. Sampling and
    candidate shuffling are deterministic under the recorded seed.
    """
    all_items = set(item_universe)
    negative_count = candidate_size - 1
    sessions: list[RecommendationSession] = []

    for user_id in selected_users:
        history = histories[user_id]
        user_items = {row.asin for row in history}
        negative_pool = sorted(all_items - user_items)
        if len(negative_pool) < negative_count:
            raise ValueError(
                f"User {user_id!r} has only {len(negative_pool)} available negatives, "
                f"but {negative_count} are required"
            )

        for target_index in range(min_history, len(history)):
            target = history[target_index]
            rng = random.Random(_stable_int_seed(candidate_seed, user_id, target_index))
            negatives = rng.sample(negative_pool, negative_count)
            candidates = negatives + [target.asin]
            rng.shuffle(candidates)

            sessions.append(
                RecommendationSession(
                    session_id=f"{user_id}:{target_index + 1}",
                    user_id=user_id,
                    target_position=target_index + 1,
                    target_asin=target.asin,
                    candidate_asins=tuple(candidates),
                )
            )

    return sessions


def validate_sessions(
    sessions: Iterable[RecommendationSession],
    histories: dict[str, list[CanonicalInteraction]],
    candidate_size: int,
) -> None:
    """Raise AssertionError if leakage or candidate invariants are violated."""
    for session in sessions:
        assert len(session.candidate_asins) == candidate_size
        assert len(set(session.candidate_asins)) == candidate_size
        assert session.target_asin in session.candidate_asins

        user_items = {row.asin for row in histories[session.user_id]}
        negatives = set(session.candidate_asins) - {session.target_asin}
        assert negatives.isdisjoint(user_items)
