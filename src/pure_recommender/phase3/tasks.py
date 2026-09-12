"""Build the incremental review-extraction workload for frozen sessions.

A review becomes available to PURE only after the corresponding purchase has
occurred. For a frozen recommendation session targeting purchase position ``t``,
only interactions 1..t-1 are observable. The same interaction may be observable
in many later sessions, but its review should be extracted only once and then
reused by the evolving profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ReviewExtractionTask:
    task_id: str
    user_id: str
    interaction_position: int
    interaction: Mapping[str, object]


def build_required_extraction_tasks(
    histories: Mapping[str, Sequence[Mapping[str, object]]],
    sessions: Sequence[Mapping[str, object]],
) -> list[ReviewExtractionTask]:
    """Return each review that becomes observable across the frozen sessions.

    Tasks follow the frozen session order. Within a session, newly required
    interactions are added in chronological order. A target review is never
    extracted before that purchase has occurred; it can legitimately become an
    observed review for a later recommendation session.
    """

    tasks: list[ReviewExtractionTask] = []
    seen: set[tuple[str, int]] = set()

    for session in sessions:
        user_id = str(session.get("user_id", "")).strip()
        session_id = str(session.get("session_id", "")).strip()
        if not user_id or not session_id:
            raise ValueError(f"Invalid frozen session: {session!r}")
        if user_id not in histories:
            raise ValueError(f"Session user {user_id!r} is absent from canonical histories")

        try:
            target_position = int(session["target_position"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid target position in session {session_id!r}") from exc

        history = histories[user_id]
        target_index = target_position - 1
        if target_index < 1 or target_index >= len(history):
            raise ValueError(f"Invalid target position in session {session_id!r}")

        session_target = str(session.get("target_asin", "")).strip()
        canonical_target = str(history[target_index].get("asin", "")).strip()
        if session_target != canonical_target:
            raise ValueError(
                f"Frozen target mismatch in session {session_id!r}: "
                f"session={session_target!r}, history={canonical_target!r}"
            )

        # Only positions strictly before the current target are observable.
        for interaction_index in range(target_index):
            position = interaction_index + 1
            key = (user_id, position)
            if key in seen:
                continue
            interaction = history[interaction_index]
            task_id = f"{user_id}:{position}"
            tasks.append(
                ReviewExtractionTask(
                    task_id=task_id,
                    user_id=user_id,
                    interaction_position=position,
                    interaction=interaction,
                )
            )
            seen.add(key)

    return tasks
