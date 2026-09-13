"""Generate thesis-ready analysis from the already-frozen final experiment results.

Phase 7 is intentionally a post-hoc analysis step. It does not call the LLM and
it does not modify any frozen recommendation artifact. The script reads the
final PURE, Sequential, Recency-Focused, and ICL outputs; verifies that they are
strictly aligned on the same 94 sessions and 20 users; then generates compact
CSV/JSON/Markdown/SVG artifacts for the thesis results chapter.

Statistical design
------------------
The project evaluates NDCG by first averaging sessions within each user and then
averaging users equally. The paired bootstrap in this script follows the same
unit of analysis: users are resampled with replacement, while PURE and each
baseline stay paired for every resampled user. The resulting confidence interval
is an uncertainty summary for this frozen 20-user subset. It must not be written
as proof that the subset is a random sample of the full Amazon population.
"""

from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
import tomllib
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis import (
    METHOD_ORDER,
    NDCG_KS,
    bootstrap_paired_user_delta,
    compute_per_user_ndcg,
    compute_rank_summary,
    compute_win_tie_loss,
    load_json,
    load_jsonl_rows,
    relative_improvement_percent,
    validate_aligned_results,
    write_grouped_ndcg_svg,
)
from pure_recommender.analysis.final_results import aggregate_users, write_csv
from pure_recommender.experiment_handoff import publish_handoff


EXPERIMENT = "phase7_final_analysis_v1"
CONFIG_PATH = REPO_ROOT / "config" / "phase7_final_analysis.toml"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _fmt(value: float | None, digits: int = 6) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Create a compact Markdown table with stable formatting."""

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _require_summary(summary: Mapping[str, object], method: str) -> None:
    """Reject stale, partial, or non-PASS summaries before analysis begins."""

    if summary.get("status") != "PASS":
        raise ValueError(f"{method} summary status must be PASS; found {summary.get('status')!r}")
    successful = int(summary.get("successful_sessions", 0) or 0)
    failed = int(summary.get("failed_sessions", 0) or 0)
    if successful != 94 or failed != 0:
        raise ValueError(
            f"{method} summary must be 94/94 with zero failures; "
            f"successful={successful}, failed={failed}"
        )


def _summary_ndcg(summary: Mapping[str, object], method: str) -> dict[int, float]:
    ndcg = summary.get("ndcg")
    if not isinstance(ndcg, Mapping):
        raise ValueError(f"{method} summary is missing the ndcg mapping")
    return {k: float(ndcg[str(k)]) for k in NDCG_KS}


def _usage_latency_row(method: str, summary: Mapping[str, object]) -> dict[str, object]:
    usage = summary.get("usage_totals_all_requests")
    latency = summary.get("latency")
    protocols = summary.get("protocol_counts")
    if not isinstance(usage, Mapping) or not isinstance(latency, Mapping):
        raise ValueError(f"{method} summary is missing usage/latency accounting")
    if not isinstance(protocols, Mapping):
        protocols = {}

    return {
        "method": method,
        "request_count": int(usage.get("request_count", 0) or 0),
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
        "mean_prompt_tokens": float(usage.get("mean_prompt_tokens", 0.0) or 0.0),
        "max_prompt_tokens": int(usage.get("max_prompt_tokens", 0) or 0),
        "mean_request_seconds": float(latency.get("mean_request_seconds", 0.0) or 0.0),
        "mean_session_seconds": float(latency.get("mean_session_seconds", 0.0) or 0.0),
        "median_session_seconds": float(latency.get("median_session_seconds", 0.0) or 0.0),
        "direct_primary_successes": int(protocols.get("direct_primary_successes", 0) or 0),
        "fallback_attempts": int(protocols.get("fallback_attempts", 0) or 0),
        "fallback_successes": int(protocols.get("fallback_successes", 0) or 0),
    }


def main() -> int:
    with CONFIG_PATH.open("rb") as handle:
        config = tomllib.load(handle)

    inputs_raw = config.get("inputs")
    analysis_raw = config.get("analysis", {})
    output_raw = config.get("output", {})
    if not isinstance(inputs_raw, dict):
        raise ValueError("Phase 7 config must define [inputs.<method>] sections")

    expected_sessions = int(analysis_raw.get("expected_sessions", 94))
    expected_users = int(analysis_raw.get("expected_users", 20))
    bootstrap_repetitions = int(analysis_raw.get("bootstrap_repetitions", 10000))
    bootstrap_seed = int(analysis_raw.get("bootstrap_seed", 20260913))
    output_dir = _resolve(str(output_raw.get("directory", "outputs/phase7_final_analysis_v1")))
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries: dict[str, dict[str, object]] = {}
    method_rows: dict[str, list[dict[str, object]]] = {}

    print("=" * 108)
    print("PHASE 7 — FINAL THESIS ANALYSIS")
    print("=" * 108)
    print("LLM calls                  : NONE")
    print(f"Expected frozen sessions   : {expected_sessions}")
    print(f"Expected users             : {expected_users}")
    print(f"Bootstrap repetitions      : {bootstrap_repetitions}")
    print(f"Bootstrap seed             : {bootstrap_seed}")
    print()

    for method in METHOD_ORDER:
        method_config = inputs_raw.get(method)
        if not isinstance(method_config, dict) or "directory" not in method_config:
            raise ValueError(f"Missing [inputs.{method}] directory in {CONFIG_PATH}")
        directory = _resolve(str(method_config["directory"]))
        summary_path = directory / "summary.json"
        results_path = directory / "results.jsonl"
        if not summary_path.exists():
            raise FileNotFoundError(f"Missing frozen summary for {method}: {summary_path}")
        if not results_path.exists():
            raise FileNotFoundError(f"Missing frozen results for {method}: {results_path}")

        summary = load_json(summary_path)
        rows = load_jsonl_rows(results_path)
        _require_summary(summary, method)
        summaries[method] = summary
        method_rows[method] = rows
        print(f"{method:<18}: rows={len(rows):>3}  source={directory.relative_to(REPO_ROOT)}")

    aligned_session_ids = validate_aligned_results(
        method_rows,
        expected_sessions=expected_sessions,
    )

    per_user_by_method = {
        method: compute_per_user_ndcg(method_rows[method]) for method in METHOD_ORDER
    }
    user_sets = {method: set(values) for method, values in per_user_by_method.items()}
    reference_users = user_sets[METHOD_ORDER[0]]
    if len(reference_users) != expected_users:
        raise ValueError(
            f"Expected {expected_users} users after aggregation; found {len(reference_users)}"
        )
    for method in METHOD_ORDER[1:]:
        if user_sets[method] != reference_users:
            raise ValueError(f"User set mismatch between Sequential and {method}")

    # Recompute the final aggregate from raw result rows and verify it against the
    # frozen summary. This catches accidental use of a historical/non-final file.
    final_scores: dict[str, dict[int, float]] = {}
    for method in METHOD_ORDER:
        recomputed = aggregate_users(per_user_by_method[method])
        frozen = _summary_ndcg(summaries[method], method)
        for k in NDCG_KS:
            if abs(recomputed[k] - frozen[k]) > 1e-12:
                raise ValueError(
                    f"{method} NDCG@{k} mismatch between results.jsonl and summary.json: "
                    f"recomputed={recomputed[k]!r}, frozen={frozen[k]!r}"
                )
        final_scores[method] = recomputed

    # -------------------------------------------------------------------------
    # Main comparison table and PURE improvements.
    # -------------------------------------------------------------------------
    comparison_rows: list[dict[str, object]] = []
    for method in METHOD_ORDER:
        comparison_rows.append(
            {
                "method": method,
                **{f"ndcg_at_{k}": final_scores[method][k] for k in NDCG_KS},
            }
        )
    write_csv(
        output_dir / "final_comparison.csv",
        ["method", *[f"ndcg_at_{k}" for k in NDCG_KS]],
        comparison_rows,
    )

    improvement_rows: list[dict[str, object]] = []
    for baseline in METHOD_ORDER[:-1]:
        for k in NDCG_KS:
            pure = final_scores["PURE"][k]
            base = final_scores[baseline][k]
            improvement_rows.append(
                {
                    "baseline": baseline,
                    "k": k,
                    "baseline_ndcg": base,
                    "pure_ndcg": pure,
                    "absolute_delta": pure - base,
                    "relative_improvement_percent": relative_improvement_percent(pure, base),
                }
            )
    write_csv(
        output_dir / "pure_improvements.csv",
        [
            "baseline",
            "k",
            "baseline_ndcg",
            "pure_ndcg",
            "absolute_delta",
            "relative_improvement_percent",
        ],
        improvement_rows,
    )

    # -------------------------------------------------------------------------
    # Per-user table, paired bootstrap, and user-level win/tie/loss counts.
    # -------------------------------------------------------------------------
    per_user_rows: list[dict[str, object]] = []
    for user_id in sorted(reference_users):
        row: dict[str, object] = {"user_id": user_id}
        for method in METHOD_ORDER:
            for k in NDCG_KS:
                normalized_method = method.lower().replace("-", "_")
                row[f"{normalized_method}_ndcg_at_{k}"] = per_user_by_method[method][user_id][k]
        per_user_rows.append(row)

    per_user_fields = ["user_id"]
    for method in METHOD_ORDER:
        normalized_method = method.lower().replace("-", "_")
        per_user_fields.extend(f"{normalized_method}_ndcg_at_{k}" for k in NDCG_KS)
    write_csv(output_dir / "per_user_ndcg.csv", per_user_fields, per_user_rows)

    bootstrap_rows: list[dict[str, object]] = []
    win_loss_rows: list[dict[str, object]] = []
    for baseline in METHOD_ORDER[:-1]:
        for k in NDCG_KS:
            bootstrap = bootstrap_paired_user_delta(
                per_user_by_method["PURE"],
                per_user_by_method[baseline],
                k=k,
                repetitions=bootstrap_repetitions,
                seed=bootstrap_seed,
                label=baseline,
            )
            bootstrap_rows.append({"baseline": baseline, "k": k, **bootstrap})
            win_loss_rows.append(
                {
                    "baseline": baseline,
                    "k": k,
                    **compute_win_tie_loss(
                        per_user_by_method["PURE"],
                        per_user_by_method[baseline],
                        k=k,
                    ),
                }
            )

    write_csv(
        output_dir / "paired_bootstrap.csv",
        [
            "baseline",
            "k",
            "users",
            "repetitions",
            "observed_mean_delta",
            "ci95_lower",
            "ci95_upper",
            "bootstrap_fraction_positive",
            "bootstrap_fraction_negative",
        ],
        bootstrap_rows,
    )
    write_csv(
        output_dir / "pure_user_win_tie_loss.csv",
        ["baseline", "k", "wins", "ties", "losses"],
        win_loss_rows,
    )

    # -------------------------------------------------------------------------
    # Rank behavior and computational cost summaries.
    # -------------------------------------------------------------------------
    rank_rows: list[dict[str, object]] = []
    usage_rows: list[dict[str, object]] = []
    for method in METHOD_ORDER:
        rank_rows.append({"method": method, **compute_rank_summary(method_rows[method])})
        usage_rows.append(_usage_latency_row(method, summaries[method]))

    write_csv(
        output_dir / "rank_summary.csv",
        [
            "method",
            "sessions",
            "mean_rank",
            "median_rank",
            "best_rank",
            "worst_rank",
            "top1_rate",
            "top5_rate",
            "top10_rate",
            "top20_rate",
        ],
        rank_rows,
    )
    write_csv(
        output_dir / "usage_latency.csv",
        [
            "method",
            "request_count",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "mean_prompt_tokens",
            "max_prompt_tokens",
            "mean_request_seconds",
            "mean_session_seconds",
            "median_session_seconds",
            "direct_primary_successes",
            "fallback_attempts",
            "fallback_successes",
        ],
        usage_rows,
    )

    write_grouped_ndcg_svg(output_dir / "final_comparison.svg", final_scores)

    # -------------------------------------------------------------------------
    # Human-readable report. The generated report is intentionally local because
    # outputs/ is gitignored; only a compact handoff summary is pushed.
    # -------------------------------------------------------------------------
    main_table = _markdown_table(
        ["روش", "NDCG@1", "NDCG@5", "NDCG@10", "NDCG@20"],
        [
            [method, *[_fmt(final_scores[method][k]) for k in NDCG_KS]]
            for method in METHOD_ORDER
        ],
    )

    improvement_table_rows: list[list[str]] = []
    for item in improvement_rows:
        improvement_table_rows.append(
            [
                str(item["baseline"]),
                f"@{item['k']}",
                _fmt(float(item["absolute_delta"])),
                (
                    "N/A"
                    if item["relative_improvement_percent"] is None
                    else f"{float(item['relative_improvement_percent']):.2f}%"
                ),
            ]
        )
    improvement_table = _markdown_table(
        ["Baseline", "Cutoff", "اختلاف مطلق PURE", "بهبود نسبی PURE"],
        improvement_table_rows,
    )

    bootstrap_table = _markdown_table(
        ["Baseline", "Cutoff", "Δ مشاهده‌شده", "95% CI", "Bootstrap P(Δ>0)"],
        [
            [
                str(row["baseline"]),
                f"@{row['k']}",
                _fmt(float(row["observed_mean_delta"])),
                f"[{_fmt(float(row['ci95_lower']))}, {_fmt(float(row['ci95_upper']))}]",
                f"{100.0 * float(row['bootstrap_fraction_positive']):.2f}%",
            ]
            for row in bootstrap_rows
        ],
    )

    win_loss_table = _markdown_table(
        ["Baseline", "Cutoff", "برد PURE", "مساوی", "باخت PURE"],
        [
            [
                str(row["baseline"]),
                f"@{row['k']}",
                str(row["wins"]),
                str(row["ties"]),
                str(row["losses"]),
            ]
            for row in win_loss_rows
        ],
    )

    rank_table = _markdown_table(
        ["روش", "Mean Rank", "Median Rank", "Top-1", "Top-5", "Top-10"],
        [
            [
                str(row["method"]),
                _fmt(float(row["mean_rank"]), 3),
                _fmt(float(row["median_rank"]), 3),
                f"{100.0 * float(row['top1_rate']):.2f}%",
                f"{100.0 * float(row['top5_rate']):.2f}%",
                f"{100.0 * float(row['top10_rate']):.2f}%",
            ]
            for row in rank_rows
        ],
    )

    report = f"""# Phase 7 — تحلیل نهایی نتایج پایان‌نامه

## وضعیت

**PASS — تحلیل قطعی روی خروجی‌های Frozen**

این مرحله هیچ فراخوانی مدل زبانی انجام نمی‌دهد و فقط خروجی‌های نهایی و Freeze‌شده چهار روش را تحلیل می‌کند. هر چهار روش روی همان {expected_sessions} سشن و {expected_users} کاربر اعتبارسنجی و هم‌تراز شدند.

## جدول اصلی

{main_table}

## بهبود PURE نسبت به Baselineها

{improvement_table}

## عدم‌قطعیت با Paired User-Level Bootstrap

Bootstrap با {bootstrap_repetitions:,} تکرار و seed برابر `{bootstrap_seed}` انجام شده است. واحد بازنمونه‌گیری **کاربر** است، نه سشن؛ بنابراین با روش تجمیع نهایی پروژه سازگار است.

{bootstrap_table}

> تفسیر علمی: این بازه‌ها عدم‌قطعیت اختلاف روش‌ها را در همین زیرمجموعه Frozen شامل ۲۰ کاربر توصیف می‌کنند. این تحلیل به‌تنهایی اثبات نمی‌کند که ۲۰ کاربر نمونه تصادفی از کل جمعیت Amazon هستند و نباید به‌عنوان استنباط جمعیتی بدون قید گزارش شود.

## برد / مساوی / باخت PURE در سطح کاربر

{win_loss_table}

## خلاصه رتبه هدف

{rank_table}

## فایل‌های خروجی

- `final_comparison.csv`: جدول اصلی NDCG
- `pure_improvements.csv`: اختلاف مطلق و درصد بهبود PURE
- `paired_bootstrap.csv`: Paired bootstrap در سطح کاربر
- `pure_user_win_tie_loss.csv`: برد/مساوی/باخت در سطح کاربر
- `per_user_ndcg.csv`: NDCG هر کاربر برای هر روش
- `rank_summary.csv`: خلاصه رتبه هدف
- `usage_latency.csv`: هزینه توکن و latency
- `final_comparison.svg`: نمودار برداری مناسب Word/پایان‌نامه
- `analysis_summary.json`: خلاصه ماشین‌خوان

## برچسب علمی نتایج

تمام این نتایج مربوط به مدل مشتق محلی `llama-3.2-3b-instruct-uncensored` و زیرمجموعه Frozen پروژه هستند و نباید به‌عنوان بازتولید دقیق checkpoint یا اعداد کامل مقاله اصلی معرفی شوند.
"""
    (output_dir / "analysis_report.md").write_text(report, encoding="utf-8")

    compact_bootstrap = [
        {
            "baseline": row["baseline"],
            "k": row["k"],
            "delta": row["observed_mean_delta"],
            "ci95": [row["ci95_lower"], row["ci95_upper"]],
            "fraction_positive": row["bootstrap_fraction_positive"],
        }
        for row in bootstrap_rows
    ]
    compact_improvements = [
        {
            "baseline": row["baseline"],
            "k": row["k"],
            "absolute_delta": row["absolute_delta"],
            "relative_percent": row["relative_improvement_percent"],
        }
        for row in improvement_rows
    ]

    analysis_summary: dict[str, object] = {
        "experiment": EXPERIMENT,
        "status": "PASS",
        "llm_calls": 0,
        "aligned_sessions": len(aligned_session_ids),
        "users": len(reference_users),
        "bootstrap": {
            "unit": "user",
            "repetitions": bootstrap_repetitions,
            "seed": bootstrap_seed,
            "interpretation_scope": "frozen_20_user_subset_not_population_random_sample_claim",
        },
        "final_ndcg": {
            method: {str(k): final_scores[method][k] for k in NDCG_KS}
            for method in METHOD_ORDER
        },
        "pure_improvements": compact_improvements,
        "paired_bootstrap": compact_bootstrap,
        "output_directory": str(output_dir.relative_to(REPO_ROOT)),
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(analysis_summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    handoff_payload = {
        "state": "RESULT",
        "experiment": EXPERIMENT,
        "summary": analysis_summary,
        "recommended_uploads_if_detailed_review_is_needed": [
            str((output_dir / "analysis_report.md").relative_to(REPO_ROOT)),
            str((output_dir / "paired_bootstrap.csv").relative_to(REPO_ROOT)),
            str((output_dir / "analysis_summary.json").relative_to(REPO_ROOT)),
        ],
    }
    ok, message = publish_handoff(
        REPO_ROOT,
        handoff_payload,
        commit_message="handoff: phase7 final thesis analysis",
        auto_push=True,
    )

    print()
    print("=" * 108)
    print("PHASE 7 SUMMARY")
    print("=" * 108)
    for method in METHOD_ORDER:
        scores = " / ".join(f"{final_scores[method][k]:.6f}" for k in NDCG_KS)
        print(f"{method:<18}: {scores}")
    print(f"analysis output           : {output_dir}")
    print(f"handoff                   : {'OK' if ok else 'WARNING'} — {message}")
    print("status                    : PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
