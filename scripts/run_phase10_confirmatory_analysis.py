"""Run the pre-declared Phase 10C confirmatory analysis.

The primary endpoint is PURE vs Recency-Focused on user-level NDCG@10 using a
paired two-sided t-test at alpha=0.05. One PURE session remained structurally
unresolved while effectiveness metrics were still blinded. The frozen missing-
output policy assigns that session NDCG@10=0 for the primary analysis and reports
observed-only and optimistic-rank-1 sensitivity views separately.
"""

from __future__ import annotations

from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.evaluation.metrics import ndcg_at_ks_from_rank
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.phase10_analysis_contract import (
    PRIMARY_ALPHA,
    PRIMARY_CONFIDENCE,
    PRIMARY_METHOD_A,
    PRIMARY_METHOD_B,
    PRIMARY_METRIC,
    PRIMARY_TEST,
    PRIMARY_UNIT,
    PRIMARY_USERS,
)
from pure_recommender.phase2 import load_sessions

EXPERIMENT = "phase10_confirmatory_analysis_v1"
EXPECTED_SESSIONS = 767
EXPECTED_UNRESOLVED_SESSION = "A3C8IUK92R6137:13"
RECENCY_RESULTS = REPO_ROOT / "outputs/phase10_confirmatory_recency_v1/results.jsonl"
PURE_RESULTS = REPO_ROOT / "outputs/phase10_confirmatory_pure_v1/results.jsonl"
SESSIONS_PATH = REPO_ROOT / "outputs/phase9_confirmatory_cohort_v1/sessions.jsonl.gz"
OUTPUT_DIR = REPO_ROOT / "outputs/phase10_confirmatory_analysis_v1"


def _load_latest(path: Path) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError(f"Expected JSON object at {path}:{line_number}")
            session_id = row.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise RuntimeError(f"Missing session_id at {path}:{line_number}")
            latest[session_id] = row
    return latest


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function."""

    max_iterations = 300
    eps = 3.0e-14
    fpmin = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise RuntimeError("Incomplete-beta continued fraction did not converge")


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _student_t_cdf(t_value: float, df: int) -> float:
    if df < 1:
        raise ValueError("df must be positive")
    if t_value == 0.0:
        return 0.5
    x = df / (df + t_value * t_value)
    tail = 0.5 * _regularized_beta(x, df / 2.0, 0.5)
    return 1.0 - tail if t_value > 0 else tail


def _t_critical_two_sided(alpha: float, df: int) -> float:
    target = 1.0 - alpha / 2.0
    low, high = 0.0, 20.0
    for _ in range(100):
        mid = (low + high) / 2.0
        if _student_t_cdf(mid, df) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _paired_test(differences: list[float]) -> dict[str, object]:
    n = len(differences)
    if n < 2:
        raise ValueError("Paired test requires at least two users")
    mean_delta = statistics.mean(differences)
    sd_delta = statistics.stdev(differences)
    se = sd_delta / math.sqrt(n)
    if se == 0.0:
        t_stat = math.inf if mean_delta > 0 else (-math.inf if mean_delta < 0 else 0.0)
        p_value = 0.0 if mean_delta != 0 else 1.0
    else:
        t_stat = mean_delta / se
        cdf = _student_t_cdf(abs(t_stat), n - 1)
        p_value = max(0.0, min(1.0, 2.0 * (1.0 - cdf)))
    t_crit = _t_critical_two_sided(PRIMARY_ALPHA, n - 1)
    margin = t_crit * se
    return {
        "n_users": n,
        "mean_delta": mean_delta,
        "sd_delta": sd_delta,
        "standard_error": se,
        "t_statistic": t_stat,
        "degrees_of_freedom": n - 1,
        "p_value_two_sided": p_value,
        "confidence_level": PRIMARY_CONFIDENCE,
        "ci_lower": mean_delta - margin,
        "ci_upper": mean_delta + margin,
        "alpha": PRIMARY_ALPHA,
        "reject_null": bool(p_value < PRIMARY_ALPHA),
    }


def _session_ndcg(row: Mapping[str, object], k: int) -> float:
    ndcg = row.get("ndcg")
    if not isinstance(ndcg, Mapping):
        raise RuntimeError(f"Missing ndcg mapping for session {row.get('session_id')}")
    value = ndcg.get(str(k))
    if not isinstance(value, (int, float)):
        raise RuntimeError(f"Missing NDCG@{k} for session {row.get('session_id')}")
    return float(value)


def _user_means(values: Mapping[str, list[float]]) -> dict[str, float]:
    return {user_id: statistics.mean(rows) for user_id, rows in values.items()}


def _method_user_ndcg(
    sessions: list[dict[str, object]],
    rows: Mapping[str, dict[str, object]],
    *,
    k: int,
    missing_rank: int | None,
) -> dict[str, float]:
    by_user: dict[str, list[float]] = defaultdict(list)
    for session in sessions:
        session_id = str(session["session_id"])
        user_id = str(session["user_id"])
        row = rows.get(session_id)
        if row is not None and row.get("status") == "ok":
            by_user[user_id].append(_session_ndcg(row, k))
            continue
        if missing_rank is None:
            continue
        by_user[user_id].append(float(ndcg_at_ks_from_rank(missing_rank)[k]))
    return _user_means(by_user)


def _paired_view(
    recency_users: Mapping[str, float],
    pure_users: Mapping[str, float],
) -> tuple[list[str], list[float]]:
    users = sorted(set(recency_users) & set(pure_users))
    if len(users) != PRIMARY_USERS:
        raise RuntimeError(f"Expected {PRIMARY_USERS} paired users; found {len(users)}")
    return users, [pure_users[user] - recency_users[user] for user in users]


def main() -> int:
    sessions = load_sessions(SESSIONS_PATH)
    if len(sessions) != EXPECTED_SESSIONS:
        raise RuntimeError(f"Expected {EXPECTED_SESSIONS} frozen sessions; found {len(sessions)}")
    if len({str(row['user_id']) for row in sessions}) != PRIMARY_USERS:
        raise RuntimeError("Frozen session user count mismatch")

    recency = _load_latest(RECENCY_RESULTS)
    pure = _load_latest(PURE_RESULTS)
    frozen_ids = {str(row["session_id"]) for row in sessions}
    if set(recency) != frozen_ids:
        raise RuntimeError("Recency latest rows do not cover exactly the frozen sessions")
    recency_bad = [sid for sid, row in recency.items() if row.get("status") != "ok"]
    if recency_bad:
        raise RuntimeError(f"Recency contains unresolved sessions: {recency_bad[:10]}")

    pure_unresolved = sorted(
        sid for sid in frozen_ids if sid not in pure or pure[sid].get("status") != "ok"
    )
    if pure_unresolved != [EXPECTED_UNRESOLVED_SESSION]:
        raise RuntimeError(
            f"Expected exactly the frozen unresolved PURE session {EXPECTED_UNRESOLVED_SESSION}; "
            f"found {pure_unresolved}"
        )

    recency_users = _method_user_ndcg(sessions, recency, k=10, missing_rank=None)
    pure_primary_users = _method_user_ndcg(sessions, pure, k=10, missing_rank=20)
    pure_observed_users = _method_user_ndcg(sessions, pure, k=10, missing_rank=None)
    pure_optimistic_users = _method_user_ndcg(sessions, pure, k=10, missing_rank=1)

    users, primary_differences = _paired_view(recency_users, pure_primary_users)
    _, observed_differences = _paired_view(recency_users, pure_observed_users)
    _, optimistic_differences = _paired_view(recency_users, pure_optimistic_users)

    primary_test = _paired_test(primary_differences)
    observed_test = _paired_test(observed_differences)
    optimistic_test = _paired_test(optimistic_differences)

    method_metrics: dict[str, dict[str, float]] = {}
    for label, rows, missing_rank in (
        ("recency", recency, None),
        ("pure_conservative", pure, 20),
        ("pure_observed_only", pure, None),
        ("pure_optimistic_bound", pure, 1),
    ):
        per_k: dict[str, float] = {}
        for k in (1, 5, 10, 20):
            user_values = _method_user_ndcg(sessions, rows, k=k, missing_rank=missing_rank)
            if len(user_values) != PRIMARY_USERS:
                raise RuntimeError(f"{label} NDCG@{k} does not contain {PRIMARY_USERS} users")
            per_k[str(k)] = statistics.mean(user_values.values())
        method_metrics[label] = per_k

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    user_csv = OUTPUT_DIR / "user_level_primary.csv"
    with user_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user_id", "recency_ndcg10", "pure_ndcg10_conservative", "delta"])
        for user in users:
            writer.writerow([
                user,
                recency_users[user],
                pure_primary_users[user],
                pure_primary_users[user] - recency_users[user],
            ])

    summary: dict[str, object] = {
        "experiment": EXPERIMENT,
        "status": "PASS",
        "confirmatory_effectiveness_metrics_inspected": True,
        "contract": {
            "method_a": PRIMARY_METHOD_A,
            "method_b": PRIMARY_METHOD_B,
            "metric": PRIMARY_METRIC,
            "unit": PRIMARY_UNIT,
            "test": PRIMARY_TEST,
            "alpha": PRIMARY_ALPHA,
            "users": PRIMARY_USERS,
        },
        "workload": {
            "sessions": EXPECTED_SESSIONS,
            "pure_successful_sessions": EXPECTED_SESSIONS - 1,
            "pure_unresolved_sessions": [EXPECTED_UNRESOLVED_SESSION],
        },
        "primary_missing_output_policy": {
            "session_id": EXPECTED_UNRESOLVED_SESSION,
            "pure_imputed_rank": 20,
            "pure_imputed_ndcg10": 0.0,
            "rationale": "blinded worst-case NDCG@10 contribution; cannot favor PURE",
        },
        "method_user_equal_ndcg": method_metrics,
        "primary_test": primary_test,
        "sensitivity": {
            "observed_only": observed_test,
            "optimistic_rank1_bound": optimistic_test,
        },
    }
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    payload = {
        "state": "RESULT",
        "experiment": EXPERIMENT,
        "confirmatory_effectiveness_metrics_inspected": True,
        "summary": summary,
    }
    ok, detail = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message="handoff: phase10 confirmatory analysis result",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {detail}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
