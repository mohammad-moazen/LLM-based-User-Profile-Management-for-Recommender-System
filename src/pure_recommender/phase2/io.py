"""Read the frozen Phase 1 artifacts used by Phase 2.

The public interaction artifact is already written by Phase 1 in canonical
(user, chronological-timestamp, deterministic tie-break) order. We therefore
preserve file order within each user instead of re-sorting the public rows and
risking a different order for equal timestamps after ``source_row_index`` has
been removed from the exported schema.
"""

from __future__ import annotations

from collections import defaultdict
import gzip
import json
from pathlib import Path
from typing import Iterator


def _iter_jsonl_gz(path: Path) -> Iterator[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object in {path} at line {line_number}")
            yield row


def load_items(path: Path) -> dict[str, str]:
    """Load the canonical Phase 1 ASIN -> title mapping."""

    items: dict[str, str] = {}
    for row in _iter_jsonl_gz(path):
        asin = str(row.get("asin", "")).strip()
        title = str(row.get("title", "")).strip()
        if not asin or not title:
            raise ValueError(f"Invalid canonical item row in {path}: {row!r}")
        previous = items.get(asin)
        if previous is not None and previous != title:
            raise ValueError(f"Conflicting titles for ASIN {asin!r} in {path}")
        items[asin] = title
    return items


def load_histories(path: Path) -> dict[str, list[dict[str, object]]]:
    """Group exported canonical interactions while preserving Phase 1 order."""

    histories: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _iter_jsonl_gz(path):
        user_id = str(row.get("user_id", "")).strip()
        asin = str(row.get("asin", "")).strip()
        title = str(row.get("title", "")).strip()
        if not user_id or not asin or not title:
            raise ValueError(f"Invalid canonical interaction row in {path}: {row!r}")
        histories[user_id].append(row)
    return dict(histories)


def load_sessions(path: Path) -> list[dict[str, object]]:
    """Load the frozen deterministic recommendation sessions."""

    sessions: list[dict[str, object]] = []
    for row in _iter_jsonl_gz(path):
        required = ("session_id", "user_id", "target_position", "target_asin", "candidate_asins")
        if any(key not in row for key in required):
            raise ValueError(f"Invalid session row in {path}: {row!r}")
        candidates = row["candidate_asins"]
        if not isinstance(candidates, list) or not all(isinstance(value, str) for value in candidates):
            raise ValueError(f"Invalid candidate list in {path}: {row!r}")
        sessions.append(row)
    return sessions
