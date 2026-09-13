"""Deterministic analysis helpers for the frozen thesis comparison.

This module intentionally depends only on the Python standard library. The final
analysis must be easy to rerun on the same Windows environment that produced the
frozen recommendation artifacts, without introducing a new scientific software
stack after the experiments have already been completed.

The statistical unit used by the project is the user: session-level NDCG values
are first averaged within each user and then users are averaged equally. The
paired bootstrap implemented here therefore resamples users, not sessions. This
matches the final evaluation aggregation and avoids giving users with longer
histories disproportionate influence.
"""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
from html import escape
import json
import math
from pathlib import Path
import random
import statistics
from typing import Iterable, Mapping, Sequence


NDCG_KS: tuple[int, ...] = (1, 5, 10, 20)
METHOD_ORDER: tuple[str, ...] = ("Sequential", "Recency-Focused", "ICL", "PURE")


def load_json(path: Path) -> dict[str, object]:
    """Load one JSON object and fail loudly on unexpected top-level content."""

    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}; found {type(value).__name__}")
    return value


def load_jsonl_rows(path: Path) -> list[dict[str, object]]:
    """Load JSONL rows while preserving file order.

    The final experiment runners write exactly one terminal row per session in a
    clean rerun. We still validate every line so analysis cannot silently proceed
    if a local artifact is truncated or manually edited.
    """

    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected object row in {path} at line {line_number}")
            rows.append(value)
    return rows


def validate_aligned_results(
    method_rows: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    expected_sessions: int = 94,
) -> list[str]:
    """Validate that all methods contain the same successful frozen sessions.

    This is a critical guard for paired analysis. A comparison must never mix a
    94-session PURE result with a baseline that silently dropped one malformed
    model response. Every method must have one successful row for every session,
    and the session ID sets must match exactly.
    """

    if set(method_rows) != set(METHOD_ORDER):
        raise ValueError(
            f"Expected methods {METHOD_ORDER!r}; found {tuple(method_rows)!r}"
        )

    session_ids_by_method: dict[str, list[str]] = {}
    for method in METHOD_ORDER:
        rows = list(method_rows[method])
        if len(rows) != expected_sessions:
            raise ValueError(
                f"{method} must contain {expected_sessions} rows; found {len(rows)}"
            )

        ids: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if row.get("status") != "ok":
                raise ValueError(
                    f"{method} contains a non-ok analysis row for {row.get('session_id')!r}"
                )
            session_id = str(row.get("session_id", "")).strip()
            user_id = str(row.get("user_id", "")).strip()
            if not session_id or not user_id:
                raise ValueError(f"{method} row is missing session_id/user_id: {row!r}")
            if session_id in seen:
                raise ValueError(f"{method} contains duplicate session_id {session_id!r}")
            seen.add(session_id)
            ids.append(session_id)

            rank = row.get("target_rank")
            if not isinstance(rank, int) or isinstance(rank, bool) or not 1 <= rank <= 20:
                raise ValueError(
                    f"{method} session {session_id!r} has invalid target_rank {rank!r}"
                )

            ndcg = row.get("ndcg")
            if not isinstance(ndcg, Mapping):
                raise ValueError(f"{method} session {session_id!r} is missing NDCG values")
            for k in NDCG_KS:
                value = ndcg.get(str(k))
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValueError(
                        f"{method} session {session_id!r} has invalid NDCG@{k}: {value!r}"
                    )

        session_ids_by_method[method] = ids

    reference = set(session_ids_by_method[METHOD_ORDER[0]])
    for method in METHOD_ORDER[1:]:
        actual = set(session_ids_by_method[method])
        if actual != reference:
            missing = sorted(reference - actual)
            extra = sorted(actual - reference)
            raise ValueError(
                f"Session mismatch for {method}; missing={missing[:10]}, extra={extra[:10]}"
            )

    # Returning sorted IDs makes downstream paired reports deterministic even if
    # one local JSONL file happens to have a different physical line order.
    return sorted(reference)


def compute_per_user_ndcg(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, dict[int, float]]:
    """Aggregate session NDCG within each user, matching project evaluation."""

    buckets: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: {k: [] for k in NDCG_KS}
    )
    for row in rows:
        user_id = str(row["user_id"])
        ndcg = row["ndcg"]
        if not isinstance(ndcg, Mapping):
            raise ValueError(f"Missing NDCG mapping for user {user_id!r}")
        for k in NDCG_KS:
            buckets[user_id][k].append(float(ndcg[str(k)]))

    return {
        user_id: {k: statistics.mean(values[k]) for k in NDCG_KS}
        for user_id, values in sorted(buckets.items())
    }


def aggregate_users(per_user: Mapping[str, Mapping[int, float]]) -> dict[int, float]:
    """Average already-aggregated user metrics with equal user weight."""

    if not per_user:
        raise ValueError("Cannot aggregate an empty per-user mapping")
    return {
        k: statistics.mean(float(values[k]) for values in per_user.values())
        for k in NDCG_KS
    }


def relative_improvement_percent(new_value: float, baseline_value: float) -> float | None:
    """Return percentage improvement, or None when the baseline is exactly zero."""

    if baseline_value == 0.0:
        return None
    return ((new_value - baseline_value) / baseline_value) * 100.0


def _stable_subseed(seed: int, label: str) -> int:
    """Derive deterministic independent random streams from a master seed."""

    digest = hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    """Compute a linearly interpolated percentile without NumPy."""

    if not sorted_values:
        raise ValueError("Cannot calculate a percentile of an empty sequence")
    if not 0.0 <= percentile <= 1.0:
        raise ValueError("percentile must be between 0 and 1")
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    position = percentile * (len(sorted_values) - 1)
    low_index = math.floor(position)
    high_index = math.ceil(position)
    if low_index == high_index:
        return float(sorted_values[low_index])
    fraction = position - low_index
    low = float(sorted_values[low_index])
    high = float(sorted_values[high_index])
    return low + fraction * (high - low)


def bootstrap_paired_user_delta(
    pure_per_user: Mapping[str, Mapping[int, float]],
    baseline_per_user: Mapping[str, Mapping[int, float]],
    *,
    k: int,
    repetitions: int,
    seed: int,
    label: str,
) -> dict[str, float | int]:
    """Bootstrap the mean paired user-level PURE-minus-baseline difference.

    The confidence interval is a simple percentile interval over user-resampled
    paired differences. It is intended as an uncertainty summary for this frozen
    20-user subset, not as a claim that the subset is a random sample of all
    Amazon users. That distinction should remain explicit in thesis prose.
    """

    if repetitions < 100:
        raise ValueError("bootstrap repetitions must be at least 100")
    users = sorted(set(pure_per_user) & set(baseline_per_user))
    if set(pure_per_user) != set(baseline_per_user):
        raise ValueError("PURE and baseline user sets must be identical for paired bootstrap")
    if not users:
        raise ValueError("No users available for paired bootstrap")

    deltas = [float(pure_per_user[user][k]) - float(baseline_per_user[user][k]) for user in users]
    observed = statistics.mean(deltas)

    rng = random.Random(_stable_subseed(seed, f"{label}:ndcg@{k}"))
    bootstrap_means: list[float] = []
    n = len(users)
    for _ in range(repetitions):
        # Resample user-level paired deltas with replacement. We resample indices
        # rather than two method arrays independently so each draw preserves the
        # paired experimental design.
        sample_mean = sum(deltas[rng.randrange(n)] for _ in range(n)) / n
        bootstrap_means.append(sample_mean)

    bootstrap_means.sort()
    lower = _percentile(bootstrap_means, 0.025)
    upper = _percentile(bootstrap_means, 0.975)
    positive_fraction = sum(value > 0.0 for value in bootstrap_means) / repetitions
    negative_fraction = sum(value < 0.0 for value in bootstrap_means) / repetitions

    return {
        "users": n,
        "repetitions": repetitions,
        "observed_mean_delta": observed,
        "ci95_lower": lower,
        "ci95_upper": upper,
        "bootstrap_fraction_positive": positive_fraction,
        "bootstrap_fraction_negative": negative_fraction,
    }


def compute_win_tie_loss(
    pure_per_user: Mapping[str, Mapping[int, float]],
    baseline_per_user: Mapping[str, Mapping[int, float]],
    *,
    k: int,
    tolerance: float = 1e-12,
) -> dict[str, int]:
    """Count users where PURE is better, tied, or worse at one cutoff."""

    if set(pure_per_user) != set(baseline_per_user):
        raise ValueError("User sets must match for win/tie/loss analysis")

    wins = ties = losses = 0
    for user_id in pure_per_user:
        delta = float(pure_per_user[user_id][k]) - float(baseline_per_user[user_id][k])
        if delta > tolerance:
            wins += 1
        elif delta < -tolerance:
            losses += 1
        else:
            ties += 1
    return {"wins": wins, "ties": ties, "losses": losses}


def compute_rank_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, float | int]:
    """Summarize target-rank behavior independently of discounted metrics."""

    ranks = [int(row["target_rank"]) for row in rows]
    if not ranks:
        raise ValueError("Cannot summarize ranks from an empty result set")

    return {
        "sessions": len(ranks),
        "mean_rank": statistics.mean(ranks),
        "median_rank": statistics.median(ranks),
        "best_rank": min(ranks),
        "worst_rank": max(ranks),
        "top1_rate": sum(rank <= 1 for rank in ranks) / len(ranks),
        "top5_rate": sum(rank <= 5 for rank in ranks) / len(ranks),
        "top10_rate": sum(rank <= 10 for rank in ranks) / len(ranks),
        "top20_rate": sum(rank <= 20 for rank in ranks) / len(ranks),
    }


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    """Write a UTF-8 CSV using stable column order."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_grouped_ndcg_svg(
    path: Path,
    scores: Mapping[str, Mapping[int, float]],
    *,
    title: str = "Final controlled NDCG comparison",
) -> None:
    """Generate a dependency-free grouped bar chart as an SVG file.

    SVG keeps the chart fully reproducible and publication-friendly without
    adding matplotlib to the project after the experiment phase. Word and modern
    browsers can open SVG directly, while conversion to PNG can be done later if
    a specific thesis template requires it.
    """

    width = 1200
    height = 720
    margin_left = 110
    margin_right = 50
    margin_top = 90
    margin_bottom = 110
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    maximum = max(float(scores[method][k]) for method in METHOD_ORDER for k in NDCG_KS)
    y_max = max(0.45, math.ceil(maximum * 20.0) / 20.0)

    # Deliberately use neutral, distinguishable grayscale/blue-ish browser-safe
    # values in the generated artifact. These are part of the output document,
    # not matplotlib styling state, and remain fixed for reproducibility.
    colors = {
        "Sequential": "#6B7280",
        "Recency-Focused": "#2563EB",
        "ICL": "#9CA3AF",
        "PURE": "#111827",
    }

    def y(value: float) -> float:
        return margin_top + chart_height - (value / y_max) * chart_height

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2:.1f}" y="45" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-weight="700">{escape(title)}</text>',
    ]

    # Draw horizontal reference lines at fixed 0.05 intervals to make small
    # method differences readable without visually exaggerating them.
    tick = 0.0
    while tick <= y_max + 1e-12:
        yy = y(tick)
        svg.append(
            f'<line x1="{margin_left}" y1="{yy:.2f}" x2="{width - margin_right}" y2="{yy:.2f}" stroke="#E5E7EB" stroke-width="1"/>'
        )
        svg.append(
            f'<text x="{margin_left - 15}" y="{yy + 5:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="15" fill="#374151">{tick:.2f}</text>'
        )
        tick += 0.05

    svg.append(
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + chart_height}" stroke="#111827" stroke-width="1.5"/>'
    )
    svg.append(
        f'<line x1="{margin_left}" y1="{margin_top + chart_height}" x2="{width - margin_right}" y2="{margin_top + chart_height}" stroke="#111827" stroke-width="1.5"/>'
    )

    group_width = chart_width / len(NDCG_KS)
    bar_gap = 7.0
    usable_group_width = group_width * 0.72
    bar_width = (usable_group_width - bar_gap * (len(METHOD_ORDER) - 1)) / len(METHOD_ORDER)

    for group_index, k in enumerate(NDCG_KS):
        group_center = margin_left + group_width * (group_index + 0.5)
        group_start = group_center - usable_group_width / 2
        for method_index, method in enumerate(METHOD_ORDER):
            value = float(scores[method][k])
            x = group_start + method_index * (bar_width + bar_gap)
            yy = y(value)
            bar_height = margin_top + chart_height - yy
            svg.append(
                f'<rect x="{x:.2f}" y="{yy:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="2" fill="{colors[method]}"/>'
            )
            svg.append(
                f'<text x="{x + bar_width / 2:.2f}" y="{yy - 7:.2f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#111827">{value:.3f}</text>'
            )
        svg.append(
            f'<text x="{group_center:.2f}" y="{margin_top + chart_height + 35}" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" font-weight="600">NDCG@{k}</text>'
        )

    legend_y = height - 36
    legend_total_width = 820
    legend_start = (width - legend_total_width) / 2
    item_width = legend_total_width / len(METHOD_ORDER)
    for index, method in enumerate(METHOD_ORDER):
        x = legend_start + index * item_width
        svg.append(
            f'<rect x="{x:.2f}" y="{legend_y - 14}" width="20" height="20" rx="2" fill="{colors[method]}"/>'
        )
        svg.append(
            f'<text x="{x + 30:.2f}" y="{legend_y + 2}" font-family="Arial, sans-serif" font-size="16" fill="#111827">{escape(method)}</text>'
        )

    svg.append('</svg>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")
