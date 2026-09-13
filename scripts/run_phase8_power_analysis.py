"""Run Phase 8: prospective paired-user power analysis for a new cohort.

This script is deliberately separated from the recommendation runners. It makes
zero LLM calls and never edits the frozen Phase 5/6/7 outputs. Its sole purpose
is to convert the frozen 20-user paired effects into transparent *planning*
estimates for a future evaluation on additional independent users.

Scientific guardrail
--------------------
Phase 8 is NOT a recipe for repeatedly rerunning the same users until p < 0.05.
The intended next experiment, if approved, must:

1. keep the model, prompts, preprocessing, candidates, runtime and metrics frozen;
2. use a deterministic set of NEW users that excludes the original 20;
3. keep the confirmatory primary comparison fixed in advance;
4. run the expanded cohort once under that protocol;
5. report the result even if it is not statistically significant.

The sample-size formula is a normal approximation for a paired mean effect. The
20-user pilot estimate is noisy, so the output includes both the raw calculation
and a conservative practical target with an explicit safety margin.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tomllib
from typing import Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis.power_analysis import (
    NDCG_KS,
    load_phase7_per_user_csv,
    minimum_detectable_raw_delta,
    normal_approx_power,
    normal_approx_required_n,
    paired_user_deltas,
    round_up_with_margin,
    summarize_paired_effect,
)
from pure_recommender.experiment_handoff import publish_handoff


EXPERIMENT = "phase8_power_analysis_v1"
CONFIG_PATH = REPO_ROOT / "config" / "phase8_power_analysis.toml"
BASELINES: tuple[str, ...] = ("Sequential", "Recency-Focused", "ICL")


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fieldnames)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _fmt(value: object, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    with CONFIG_PATH.open("rb") as handle:
        config = tomllib.load(handle)

    input_cfg = config.get("input", {})
    design = config.get("design", {})
    output_cfg = config.get("output", {})
    if not isinstance(input_cfg, dict) or not isinstance(design, dict):
        raise ValueError("Phase 8 config must define [input] and [design]")

    per_user_path = _resolve(str(input_cfg.get("per_user_ndcg_csv", "")))
    expected_pilot_users = int(design.get("expected_pilot_users", 20))
    alpha = float(design.get("alpha", 0.05))
    two_sided = bool(design.get("two_sided", True))
    powers = [float(value) for value in design.get("powers", [0.80, 0.90])]
    primary_baseline = str(design.get("primary_baseline", "Recency-Focused"))
    primary_k = int(design.get("primary_k", 10))
    primary_power = float(design.get("primary_power", 0.80))
    safety_margin = float(design.get("safety_margin_fraction", 0.20))
    round_to_users = int(design.get("round_to_users", 10))
    cohort_sizes = [int(value) for value in design.get("cohort_sizes", [])]
    output_dir = _resolve(str(output_cfg.get("directory", "outputs/phase8_power_analysis_v1")))
    output_dir.mkdir(parents=True, exist_ok=True)

    if primary_baseline not in BASELINES:
        raise ValueError(f"Primary baseline must be one of {BASELINES}; found {primary_baseline!r}")
    if primary_k not in NDCG_KS:
        raise ValueError(f"Primary k must be one of {NDCG_KS}; found {primary_k}")
    if primary_power not in powers:
        raise ValueError("primary_power must also appear in design.powers")
    if not two_sided:
        raise ValueError(
            "Phase 8 v1 intentionally requires a two-sided alpha to avoid changing inferential direction after seeing the pilot result"
        )

    per_user = load_phase7_per_user_csv(per_user_path)
    if len(per_user) != expected_pilot_users:
        raise ValueError(
            f"Expected exactly {expected_pilot_users} frozen pilot users; found {len(per_user)}"
        )

    print("=" * 108)
    print("PHASE 8 — PROSPECTIVE PAIRED-USER POWER ANALYSIS")
    print("=" * 108)
    print("LLM calls                  : NONE")
    print(f"Pilot users                : {len(per_user)}")
    print(f"Alpha                      : {alpha}")
    print(f"Two-sided                  : {two_sided}")
    print(f"Primary comparison         : PURE vs {primary_baseline}")
    print(f"Primary endpoint           : NDCG@{primary_k}")
    print(f"Primary target power       : {primary_power:.0%}")
    print(f"Safety margin              : {safety_margin:.0%}")
    print("Future confirmatory users  : NEW USERS ONLY; original 20 remain frozen")
    print()

    # ------------------------------------------------------------------
    # 1) Pilot paired effects and analytic sample-size estimates.
    # ------------------------------------------------------------------
    comparison_rows: list[dict[str, object]] = []
    lookup: dict[tuple[str, int], dict[str, object]] = {}

    for baseline in BASELINES:
        for k in NDCG_KS:
            deltas = paired_user_deltas(per_user, baseline=baseline, k=k)
            effect = summarize_paired_effect(deltas)
            dz_raw = effect["paired_effect_dz"]
            dz = float(dz_raw) if dz_raw is not None else 0.0
            direction_positive = float(effect["mean_delta"]) > 0.0

            row: dict[str, object] = {
                "baseline": baseline,
                "k": k,
                "pilot_users": int(effect["users"]),
                "mean_delta": float(effect["mean_delta"]),
                "sd_delta": float(effect["sd_delta"]),
                "se_delta": float(effect["se_delta"]),
                "paired_effect_dz": dz_raw,
                "pure_direction_positive": direction_positive,
            }

            for power in powers:
                label = int(round(power * 100))
                if dz_raw is None or dz == 0.0:
                    required = None
                else:
                    required = normal_approx_required_n(
                        dz,
                        alpha=alpha,
                        power=power,
                        two_sided=two_sided,
                    )
                row[f"required_n_power_{label}"] = required

            comparison_rows.append(row)
            lookup[(baseline, k)] = row

    power_fields = [
        "baseline",
        "k",
        "pilot_users",
        "mean_delta",
        "sd_delta",
        "se_delta",
        "paired_effect_dz",
        "pure_direction_positive",
        *[f"required_n_power_{int(round(power * 100))}" for power in powers],
    ]
    _write_csv(output_dir / "power_by_comparison.csv", power_fields, comparison_rows)

    primary = lookup[(primary_baseline, primary_k)]
    primary_dz_raw = primary["paired_effect_dz"]
    if primary_dz_raw is None or float(primary_dz_raw) == 0.0:
        raise RuntimeError("Primary pilot effect has zero variance/effect; sample-size planning is undefined")
    if not bool(primary["pure_direction_positive"]):
        raise RuntimeError(
            "Primary pilot effect is not positive for PURE; do not design a superiority expansion from this pilot"
        )

    primary_dz = float(primary_dz_raw)
    raw_primary_n = normal_approx_required_n(
        primary_dz,
        alpha=alpha,
        power=primary_power,
        two_sided=two_sided,
    )
    planning_target_total = round_up_with_margin(
        raw_primary_n,
        safety_margin_fraction=safety_margin,
        round_to=round_to_users,
    )
    additional_new_users_if_total_target = max(0, planning_target_total - expected_pilot_users)

    # ------------------------------------------------------------------
    # 2) Sensitivity curve for the pre-declared primary endpoint.
    # ------------------------------------------------------------------
    primary_sd = float(primary["sd_delta"])
    primary_curve_rows: list[dict[str, object]] = []
    for n_users in cohort_sizes:
        row = {
            "n_users": n_users,
            "approx_power": normal_approx_power(
                primary_dz,
                n_users,
                alpha=alpha,
                two_sided=two_sided,
            ),
        }
        for power in powers:
            label = int(round(power * 100))
            row[f"mde_raw_delta_power_{label}"] = minimum_detectable_raw_delta(
                primary_sd,
                n_users,
                alpha=alpha,
                power=power,
                two_sided=two_sided,
            )
        primary_curve_rows.append(row)

    curve_fields = [
        "n_users",
        "approx_power",
        *[f"mde_raw_delta_power_{int(round(power * 100))}" for power in powers],
    ]
    _write_csv(output_dir / "primary_power_curve.csv", curve_fields, primary_curve_rows)

    # ------------------------------------------------------------------
    # 3) Machine-readable planning record and human-readable report.
    # ------------------------------------------------------------------
    primary_plan = {
        "status": "PASS",
        "analysis_type": "pilot_informed_prospective_power_planning",
        "llm_calls": 0,
        "pilot_users": expected_pilot_users,
        "future_users_policy": "new_users_only_excluding_original_frozen_20",
        "alpha": alpha,
        "two_sided": two_sided,
        "primary_baseline": primary_baseline,
        "primary_k": primary_k,
        "primary_target_power": primary_power,
        "pilot_mean_delta": float(primary["mean_delta"]),
        "pilot_sd_delta": primary_sd,
        "pilot_paired_effect_dz": primary_dz,
        "raw_required_total_users": raw_primary_n,
        "safety_margin_fraction": safety_margin,
        "round_to_users": round_to_users,
        "practical_planning_target_total_users": planning_target_total,
        "additional_new_users_relative_to_current_20": additional_new_users_if_total_target,
        "important_interpretation": (
            "Pilot-derived sample size is a planning estimate, not a promise of significance. "
            "The future confirmatory cohort must be frozen before outcomes are inspected and reported regardless of significance."
        ),
    }
    (output_dir / "primary_plan.json").write_text(
        json.dumps(primary_plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    table_rows: list[list[str]] = []
    for row in comparison_rows:
        table_rows.append(
            [
                str(row["baseline"]),
                f"@{row['k']}",
                _fmt(float(row["mean_delta"]), 6),
                _fmt(float(row["sd_delta"]), 6),
                _fmt(row["paired_effect_dz"], 3),
                *[
                    _fmt(row[f"required_n_power_{int(round(power * 100))}"], 0)
                    for power in powers
                ],
            ]
        )

    power_headers = [
        "Baseline",
        "Cutoff",
        "Pilot Δ",
        "SD(Δ)",
        "d_z",
        *[f"N برای توان {int(round(power * 100))}%" for power in powers],
    ]

    report = f"""# Phase 8 — تحلیل توان آماری برای طراحی ارزیابی توسعه‌یافته

## وضعیت

**PASS — Planning only / No new model run**

این فاز هیچ اجرای مجددی روی ۲۰ کاربر قبلی انجام نمی‌دهد. خروجی‌های Phase 5 تا Phase 7 ثابت و Frozen باقی می‌مانند. هدف فقط این است که بر اساس اختلاف‌های جفت‌شده‌ی سطح کاربر، اندازه‌ی تقریبی یک cohort تأییدی جدید برآورد شود.

## اصل ضد p-hacking

کاربران آینده باید **کاربران جدید** باشند و ۲۰ کاربر فعلی از cohort تأییدی کنار گذاشته شوند. پروتکل مدل، prompt، preprocessing، candidate generation، seed، runtime و معیارها قبل از مشاهده نتایج cohort جدید ثابت می‌مانند. اجرای cohort جدید نباید تا زمان معنادار شدن تکرار شود؛ نتیجه، چه معنادار باشد و چه نباشد، باید گزارش شود.

## طراحی از پیش مشخص‌شده

- واحد تحلیل: کاربر
- آزمون برنامه‌ریزی: مقایسه جفت‌شده‌ی PURE و baseline
- alpha: `{alpha}` دوطرفه
- endpoint اصلی تأییدی: **PURE vs {primary_baseline}, NDCG@{primary_k}**
- توان هدف اصلی: **{primary_power:.0%}**
- تعداد کاربران pilot: **{expected_pilot_users}**

## برآوردهای Pilot

{_markdown_table(power_headers, table_rows)}

## برنامه پیشنهادی برای endpoint اصلی

برای PURE در برابر {primary_baseline} روی NDCG@{primary_k}:

- اختلاف میانگین مشاهده‌شده در pilot: **{float(primary['mean_delta']):.6f}**
- انحراف معیار اختلاف جفت‌شده: **{primary_sd:.6f}**
- اندازه اثر جفت‌شده `d_z`: **{primary_dz:.3f}**
- برآورد خام تعداد کل کاربران برای توان {primary_power:.0%}: **{raw_primary_n}**
- با حاشیه محافظه‌کارانه {safety_margin:.0%} و گردکردن رو به بالا: **{planning_target_total} کاربر**

عدد {planning_target_total} یک **هدف برنامه‌ریزی** است، نه عددی که معناداری را تضمین کند. علت حاشیه محافظه‌کارانه این است که اندازه اثر حاصل از ۲۰ کاربر می‌تواند ناپایدار یا خوش‌بینانه باشد.

## تفسیر برای پایان‌نامه

Phase 8 به‌جای تلاش برای «معنادار کردن» نتیجه فعلی، یک مطالعه توسعه‌یافته و از پیش طراحی‌شده پیشنهاد می‌کند. نتیجه Phase 7 همان‌طور که هست حفظ می‌شود: PURE بهترین point estimate را دارد ولی CIهای bootstrap فعلی صفر را قطع می‌کنند. اگر cohort جدید اجرا شود، باید به‌عنوان ارزیابی تأییدی جداگانه گزارش شود.

## فایل‌های خروجی

- `power_by_comparison.csv`
- `primary_power_curve.csv`
- `primary_plan.json`
- `phase8_report.md`
"""
    (output_dir / "phase8_report.md").write_text(report, encoding="utf-8")

    summary = {
        "experiment": EXPERIMENT,
        "status": "PASS",
        "llm_calls": 0,
        "pilot_users": expected_pilot_users,
        "primary": primary_plan,
        "all_comparisons": comparison_rows,
        "output_directory": str(output_dir.relative_to(REPO_ROOT)),
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    handoff_payload = {
        "state": "RESULT",
        "experiment": EXPERIMENT,
        "summary": {
            "status": "PASS",
            "llm_calls": 0,
            "pilot_users": expected_pilot_users,
            "alpha": alpha,
            "two_sided": two_sided,
            "primary_baseline": primary_baseline,
            "primary_k": primary_k,
            "primary_target_power": primary_power,
            "pilot_mean_delta": float(primary["mean_delta"]),
            "pilot_sd_delta": primary_sd,
            "pilot_paired_effect_dz": primary_dz,
            "raw_required_total_users": raw_primary_n,
            "practical_planning_target_total_users": planning_target_total,
            "safety_margin_fraction": safety_margin,
            "future_users_policy": "new_users_only_excluding_original_frozen_20",
            "interpretation": "planning_estimate_not_guaranteed_significance",
        },
        "recommended_uploads_if_detailed_review_is_needed": [
            str(output_dir.relative_to(REPO_ROOT) / "phase8_report.md"),
            str(output_dir.relative_to(REPO_ROOT) / "power_by_comparison.csv"),
            str(output_dir.relative_to(REPO_ROOT) / "analysis_summary.json"),
        ],
    }
    ok, message = publish_handoff(
        REPO_ROOT,
        handoff_payload,
        commit_message="handoff: phase8 prospective power analysis",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")

    print()
    print("=" * 108)
    print("PHASE 8 SUMMARY")
    print("=" * 108)
    print(f"Primary comparison        : PURE vs {primary_baseline}, NDCG@{primary_k}")
    print(f"Pilot paired effect d_z   : {primary_dz:.3f}")
    print(f"Raw N for {primary_power:.0%} power     : {raw_primary_n}")
    print(f"Practical planning target : {planning_target_total}")
    print("Policy                    : NEW USERS ONLY; do not rerun the original 20")
    print(f"Outputs                   : {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
