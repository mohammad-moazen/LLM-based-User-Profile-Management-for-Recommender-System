"""Deterministic design helpers for the Phase 9 NEW-user confirmatory cohort.

Phase 9 does not run any recommender or profile LLM. It freezes which users and
which candidate sessions a later confirmatory experiment would use. The design
continues the exact Phase 1 deterministic user-ordering rule, verifies that the
original 20 pilot users occupy the first 20 eligible positions under that rule,
and then selects the next requested users while explicitly excluding the pilot.

The candidate-generation rule is also kept identical to Phase 1: one true target
plus ``candidate_size - 1`` items sampled from the global item universe after
removing every item the user interacts with anywhere in their cleaned full
history. Sampling and shuffling use the same SHA256-derived seed convention.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Iterable, Mapping, Sequence


def stable_int_seed(*parts: object) -> int:
    """Match the stable SHA256-derived integer seed used by Phase 1."""

    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], byteorder="big", signed=False)


def eligible_user_order(
    histories: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    min_history: int,
    selection_seed: int,
) -> list[str]:
    """Return all eligible users in the exact deterministic Phase 1 order."""

    eligible = [
        user_id
        for user_id, history in histories.items()
        if len(history) >= min_history + 1
    ]
    eligible.sort(key=lambda user_id: (stable_int_seed(selection_seed, user_id), user_id))
    return eligible


def select_new_confirmatory_users(
    histories: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    pilot_user_ids: Iterable[str],
    expected_pilot_users: int,
    new_users: int,
    min_history: int,
    selection_seed: int,
) -> tuple[list[str], list[str]]:
    """Select the next deterministic eligible users after the frozen pilot.

    The guard that the original pilot equals the first ``expected_pilot_users``
    users under the Phase 1 ordering is deliberate. If the local Phase 1 artifact
    or preprocessing policy changed, Phase 9 must fail instead of silently
    constructing a cohort under a different sampling frame.
    """

    if new_users < 1:
        raise ValueError("new_users must be at least 1")
    pilot = {str(user_id) for user_id in pilot_user_ids}
    if len(pilot) != expected_pilot_users:
        raise ValueError(
            f"Expected {expected_pilot_users} unique pilot users; found {len(pilot)}"
        )

    ordered = eligible_user_order(
        histories,
        min_history=min_history,
        selection_seed=selection_seed,
    )
    expected_pilot_prefix = ordered[:expected_pilot_users]
    if set(expected_pilot_prefix) != pilot:
        missing = sorted(pilot - set(expected_pilot_prefix))
        unexpected = sorted(set(expected_pilot_prefix) - pilot)
        raise ValueError(
            "Frozen pilot users do not match the first deterministic eligible-user prefix; "
            f"missing_from_prefix={missing[:10]}, unexpected_prefix_users={unexpected[:10]}"
        )

    remaining = [user_id for user_id in ordered if user_id not in pilot]
    if len(remaining) < new_users:
        raise ValueError(
            f"Only {len(remaining)} eligible non-pilot users remain; {new_users} requested"
        )

    selected = remaining[:new_users]
    if set(selected) & pilot:
        raise AssertionError("Confirmatory cohort overlaps the frozen pilot")
    return selected, ordered


def build_confirmatory_sessions(
    histories: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    item_universe: Iterable[str],
    selected_users: Sequence[str],
    min_history: int,
    candidate_size: int,
    candidate_seed: int,
) -> list[dict[str, object]]:
    """Build deterministic Phase 1-compatible recommendation sessions."""

    if candidate_size < 2:
        raise ValueError("candidate_size must be at least 2")

    all_items = {str(item) for item in item_universe}
    negative_count = candidate_size - 1
    sessions: list[dict[str, object]] = []

    for user_id in selected_users:
        if user_id not in histories:
            raise ValueError(f"Selected user {user_id!r} is missing from histories")
        history = histories[user_id]
        if len(history) < min_history + 1:
            raise ValueError(f"Selected user {user_id!r} is not session-eligible")

        user_items = {str(row["asin"]) for row in history}
        negative_pool = sorted(all_items - user_items)
        if len(negative_pool) < negative_count:
            raise ValueError(
                f"User {user_id!r} has only {len(negative_pool)} negatives; "
                f"{negative_count} required"
            )

        for target_index in range(min_history, len(history)):
            target_asin = str(history[target_index]["asin"])
            rng = random.Random(stable_int_seed(candidate_seed, user_id, target_index))
            negatives = rng.sample(negative_pool, negative_count)
            candidates = negatives + [target_asin]
            rng.shuffle(candidates)
            sessions.append(
                {
                    "session_id": f"{user_id}:{target_index + 1}",
                    "user_id": user_id,
                    "target_position": target_index + 1,
                    "target_asin": target_asin,
                    "candidate_asins": candidates,
                }
            )

    return sessions


def validate_confirmatory_sessions(
    sessions: Sequence[Mapping[str, object]],
    histories: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    selected_users: Sequence[str],
    min_history: int,
    candidate_size: int,
) -> None:
    """Fail loudly on overlap, chronology, target, or candidate-set violations."""

    expected_count = sum(len(histories[user_id]) - min_history for user_id in selected_users)
    if len(sessions) != expected_count:
        raise ValueError(f"Expected {expected_count} sessions; found {len(sessions)}")

    selected_set = set(selected_users)
    seen_ids: set[str] = set()
    users_seen: set[str] = set()
    for session in sessions:
        session_id = str(session["session_id"])
        user_id = str(session["user_id"])
        target_position = int(session["target_position"])
        target_asin = str(session["target_asin"])
        candidates = [str(value) for value in session["candidate_asins"]]

        if session_id in seen_ids:
            raise ValueError(f"Duplicate session_id {session_id!r}")
        seen_ids.add(session_id)
        if user_id not in selected_set:
            raise ValueError(f"Session contains non-cohort user {user_id!r}")
        users_seen.add(user_id)
        if len(candidates) != candidate_size or len(set(candidates)) != candidate_size:
            raise ValueError(f"Invalid candidate cardinality for {session_id}")
        if target_asin not in candidates:
            raise ValueError(f"Target absent from candidates for {session_id}")

        target_index = target_position - 1
        history = histories[user_id]
        if target_index < min_history or target_index >= len(history):
            raise ValueError(f"Invalid target position for {session_id}")
        if str(history[target_index]["asin"]) != target_asin:
            raise ValueError(f"Target/history mismatch for {session_id}")

        user_items = {str(row["asin"]) for row in history}
        negatives = set(candidates) - {target_asin}
        if not negatives.isdisjoint(user_items):
            raise ValueError(f"Candidate leakage detected for {session_id}")

    if users_seen != selected_set:
        missing = sorted(selected_set - users_seen)
        raise ValueError(f"Selected users without sessions: {missing[:10]}")


def cohort_user_records(
    selected_users: Sequence[str],
    ordered_eligible_users: Sequence[str],
    histories: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    min_history: int,
) -> list[dict[str, object]]:
    """Create a transparent per-user cohort manifest."""

    rank_lookup = {user_id: index + 1 for index, user_id in enumerate(ordered_eligible_users)}
    records: list[dict[str, object]] = []
    for cohort_index, user_id in enumerate(selected_users, start=1):
        history_length = len(histories[user_id])
        records.append(
            {
                "cohort_index": cohort_index,
                "user_id": user_id,
                "deterministic_eligible_rank": rank_lookup[user_id],
                "history_length": history_length,
                "recommendation_sessions": history_length - min_history,
                # To recommend every target through the final purchase without
                # leakage, PURE needs profile evidence through the penultimate
                # interaction: positions 1..L-1, hence L-1 unique profile events.
                "profile_evidence_events": history_length - 1,
            }
        )
    return records


def canonical_sha256(records: Sequence[Mapping[str, object]]) -> str:
    """Hash a deterministic JSON serialization so the frozen design is auditable."""

    digest = hashlib.sha256()
    for record in records:
        payload = json.dumps(dict(record), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


__all__ = [
    "build_confirmatory_sessions",
    "canonical_sha256",
    "cohort_user_records",
    "eligible_user_order",
    "select_new_confirmatory_users",
    "stable_int_seed",
    "validate_confirmatory_sessions",
]
