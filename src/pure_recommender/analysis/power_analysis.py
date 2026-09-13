"""Pilot-informed paired power analysis for the frozen PURE thesis experiment.

Phase 8 is a planning step, not a second chance to rerun the same experiment until
it becomes significant. The functions in this module use the already-frozen
20-user paired outcomes only to estimate the scale of a future *new-user*
confirmatory cohort.

The statistical unit remains the user because the project's final metric first
averages recommendation sessions within a user and then gives every user equal
weight. Therefore effect sizes are computed from paired user-level PURE-minus-
baseline differences.

The sample-size calculation uses the standard normal approximation for a paired
mean comparison:

    n ~= ((z_(1-alpha/2) + z_power) / |d_z|)^2

where d_z is the observed paired standardized effect (mean paired difference
/ sample standard deviation of paired differences). This is intentionally
reported as a *planning estimate*, not a guarantee of future significance.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
import statistics
from statistics import NormalDist
from typing import Mapping, Sequence


NDCG_KS: tuple[int, ...] = (1, 5, 10, 20)
METHOD_COLUMN_PREFIX: dict[str, str] = {
    "Sequential": "sequential",
    "Recency-Focused": "recency_focused",
    "ICL": "icl",
    "PURE": "pure",
}


def load_phase7_per_user_csv(
    path: Path,
) -> dict[str, dict[str, dict[int, float]]]:
    """Load the Phase 7 per-user NDCG table with strict schema validation."""

    if not path.exists():
        raise FileNotFoundError(f"Phase 7 per-user table not found: {path}")

    required_columns = {"user_id"}
    for prefix in METHOD_COLUMN_PREFIX.values():
        required_columns.update(f"{prefix}_ndcg_at_{k}" for k in NDCG_KS)

    result: dict[str, dict[str, dict[int, float]]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Phase 7 per-user CSV is missing columns: {sorted(missing)}")

        for line_number, row in enumerate(reader, start=2):
            user_id = str(row.get("user_id", "")).strip()
            if not user_id:
                raise ValueError(f"Missing user_id in {path} at line {line_number}")
            if user_id in result:
                raise ValueError(f"Duplicate user_id {user_id!r} in {path}")

            methods: dict[str, dict[int, float]] = {}
            for method, prefix in METHOD_COLUMN_PREFIX.items():
                values: dict[int, float] = {}
                for k in NDCG_KS:
                    key = f"{prefix}_ndcg_at_{k}"
                    try:
                        value = float(row[key])
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"Invalid {key} for user {user_id!r} at line {line_number}"
                        ) from exc
                    if not math.isfinite(value):
                        raise ValueError(f"Non-finite {key} for user {user_id!r}")
                    values[k] = value
                methods[method] = values
            result[user_id] = methods

    if not result:
        raise ValueError(f"No users found in {path}")
    return result


def paired_user_deltas(
    per_user: Mapping[str, Mapping[str, Mapping[int, float]]],
    *,
    baseline: str,
    k: int,
) -> list[float]:
    """Return PURE-minus-baseline NDCG differences, paired by user."""

    if baseline == "PURE":
        raise ValueError("baseline must not be PURE")
    if baseline not in METHOD_COLUMN_PREFIX:
        raise ValueError(f"Unknown baseline {baseline!r}")
    if k not in NDCG_KS:
        raise ValueError(f"Unsupported NDCG cutoff {k}; expected one of {NDCG_KS}")

    deltas: list[float] = []
    for user_id in sorted(per_user):
        methods = per_user[user_id]
        if "PURE" not in methods or baseline not in methods:
            raise ValueError(f"User {user_id!r} is missing PURE or {baseline}")
        deltas.append(float(methods["PURE"][k]) - float(methods[baseline][k]))
    return deltas


def summarize_paired_effect(deltas: Sequence[float]) -> dict[str, float | int | None]:
    """Summarize one paired effect and compute pilot Cohen-style d_z."""

    values = [float(value) for value in deltas]
    if len(values) < 2:
        raise ValueError("At least two paired users are required")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Paired deltas must all be finite")

    mean_delta = statistics.mean(values)
    sd_delta = statistics.stdev(values)
    se_delta = sd_delta / math.sqrt(len(values))
    effect_size = None if sd_delta == 0.0 else mean_delta / sd_delta

    return {
        "users": len(values),
        "mean_delta": mean_delta,
        "sd_delta": sd_delta,
        "se_delta": se_delta,
        "paired_effect_dz": effect_size,
    }


def normal_approx_required_n(
    effect_size_dz: float,
    *,
    alpha: float = 0.05,
    power: float = 0.80,
    two_sided: bool = True,
) -> int:
    """Estimate required paired users under a normal approximation.

    This function is for prospective planning only. It does not turn a pilot
    estimate into evidence and it does not guarantee that a future cohort will
    be statistically significant.
    """

    if not math.isfinite(effect_size_dz) or effect_size_dz == 0.0:
        raise ValueError("effect_size_dz must be finite and non-zero")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    if not 0.5 < power < 1.0:
        raise ValueError("power must be between 0.5 and 1")

    normal = NormalDist()
    tail_alpha = alpha / 2.0 if two_sided else alpha
    z_alpha = normal.inv_cdf(1.0 - tail_alpha)
    z_power = normal.inv_cdf(power)
    estimate = ((z_alpha + z_power) / abs(effect_size_dz)) ** 2
    return max(2, math.ceil(estimate))


def normal_approx_power(
    effect_size_dz: float,
    n_users: int,
    *,
    alpha: float = 0.05,
    two_sided: bool = True,
) -> float:
    """Return approximate power for a planned paired-user sample size."""

    if n_users < 2:
        raise ValueError("n_users must be at least 2")
    if not math.isfinite(effect_size_dz):
        raise ValueError("effect_size_dz must be finite")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")

    normal = NormalDist()
    tail_alpha = alpha / 2.0 if two_sided else alpha
    z_critical = normal.inv_cdf(1.0 - tail_alpha)
    shifted_mean = abs(effect_size_dz) * math.sqrt(n_users)

    if two_sided:
        upper_rejection = 1.0 - normal.cdf(z_critical - shifted_mean)
        lower_rejection = normal.cdf(-z_critical - shifted_mean)
        return min(1.0, max(0.0, upper_rejection + lower_rejection))

    return min(1.0, max(0.0, 1.0 - normal.cdf(z_critical - shifted_mean)))


def minimum_detectable_raw_delta(
    sd_delta: float,
    n_users: int,
    *,
    alpha: float = 0.05,
    power: float = 0.80,
    two_sided: bool = True,
) -> float:
    """Approximate raw NDCG delta detectable at the requested power."""

    if sd_delta < 0.0 or not math.isfinite(sd_delta):
        raise ValueError("sd_delta must be finite and non-negative")
    if n_users < 2:
        raise ValueError("n_users must be at least 2")

    normal = NormalDist()
    tail_alpha = alpha / 2.0 if two_sided else alpha
    z_alpha = normal.inv_cdf(1.0 - tail_alpha)
    z_power = normal.inv_cdf(power)
    detectable_dz = (z_alpha + z_power) / math.sqrt(n_users)
    return detectable_dz * sd_delta


def round_up_with_margin(
    required_n: int,
    *,
    safety_margin_fraction: float,
    round_to: int,
) -> int:
    """Inflate a planning estimate and round upward to a practical cohort size."""

    if required_n < 2:
        raise ValueError("required_n must be at least 2")
    if safety_margin_fraction < 0.0:
        raise ValueError("safety_margin_fraction must be non-negative")
    if round_to < 1:
        raise ValueError("round_to must be at least 1")

    inflated = required_n * (1.0 + safety_margin_fraction)
    return int(math.ceil(inflated / round_to) * round_to)


__all__ = [
    "METHOD_COLUMN_PREFIX",
    "NDCG_KS",
    "load_phase7_per_user_csv",
    "minimum_detectable_raw_delta",
    "normal_approx_power",
    "normal_approx_required_n",
    "paired_user_deltas",
    "round_up_with_margin",
    "summarize_paired_effect",
]
