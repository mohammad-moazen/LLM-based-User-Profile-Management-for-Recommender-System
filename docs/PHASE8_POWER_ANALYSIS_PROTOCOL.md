# Phase 8 — Prospective Statistical Power Analysis Protocol

## Purpose

Phase 8 estimates the scale of a future confirmatory evaluation using the already-frozen user-level outcomes from Phase 7. It is a **study-design step**, not a mechanism for repeatedly rerunning the same experiment until a statistically significant result appears.

No LLM request is made in Phase 8. No Phase 5, Phase 6, or Phase 7 artifact is modified.

## Frozen evidence used for planning

Input:

`outputs/phase7_final_analysis_v1/per_user_ndcg.csv`

This file contains the final per-user NDCG values for the same 20 users under Sequential, Recency-Focused, ICL, and PURE.

The statistical unit is the **user**, matching the project's final evaluation rule: session-level NDCG is averaged within each user and users receive equal weight.

## Pre-declared confirmatory endpoint

The primary planning comparison is:

- method: **PURE vs Recency-Focused**
- metric: **NDCG@10**
- alpha: **0.05**
- test direction: **two-sided**
- target power: **80%**

Recency-Focused is used because it is the strongest final baseline across all four frozen cutoffs. NDCG@10 is fixed as the primary confirmatory endpoint before any expanded-user outcome is observed. Phase 8 does not alter or reinterpret the already-completed Phase 7 result.

## Sample-size method

For each baseline and cutoff, Phase 8 computes paired user-level differences:

`delta_u = NDCG_u(PURE) - NDCG_u(baseline)`

It then records:

- mean paired difference;
- sample standard deviation of paired differences;
- standard error;
- paired standardized effect `d_z = mean(delta) / SD(delta)`;
- approximate required users for 80% and 90% power.

The planning approximation is:

`n ≈ ((z_(1-alpha/2) + z_power) / |d_z|)^2`

This is a prospective normal approximation for a paired mean comparison. It is intentionally treated as a **pilot-informed planning estimate**, not a guarantee of future significance.

## Conservative planning target

Because an effect estimated from only 20 users can be unstable or optimistic, Phase 8 also reports a practical target that:

1. inflates the raw 80%-power estimate by 20%;
2. rounds upward to the next 10 users.

Both the raw estimate and the conservative target are preserved in the output so the margin is transparent rather than hidden.

## Anti-p-hacking rules for any future expanded evaluation

If an expanded evaluation is approved, the following rules must be frozen **before** looking at its outcomes:

1. The original 20 users remain frozen and are not repeatedly rerun to search for significance.
2. The confirmatory evaluation uses a deterministic set of **new users** from the remaining eligible pool.
3. Model checkpoint, prompts, Review Extractor, Profile Updater, recommendation protocol, preprocessing, candidate construction, runtime settings, generation settings, metric definitions, and output validation remain unchanged unless a change is explicitly declared as a new experiment.
4. The primary endpoint remains PURE vs Recency-Focused at NDCG@10.
5. The planned sample size is fixed before the new outcomes are inspected.
6. The expanded experiment is reported regardless of whether its confidence interval excludes zero.
7. Adding users after inspecting interim significance is not permitted unless a separate sequential-analysis design is specified in advance.
8. Secondary NDCG cutoffs and other baselines remain secondary analyses and must not be selectively promoted after seeing their p-values or confidence intervals.

## Outputs

Phase 8 writes locally to:

`outputs/phase8_power_analysis_v1/`

Expected files:

- `power_by_comparison.csv`
- `primary_power_curve.csv`
- `primary_plan.json`
- `phase8_report.md`
- `analysis_summary.json`

The output directory remains untracked because `outputs/` is intentionally gitignored. A compact result is published through `handoff/latest.json`.

## Interpretation rule

The correct interpretation is:

> The frozen 20-user experiment supplies an initial estimate of paired effect size and variance. Phase 8 uses that estimate to plan a larger, independently evaluated cohort. The resulting required sample size is uncertain because it is itself estimated from a small pilot.

The incorrect interpretation is:

> This number of users will make the result statistically significant.

Statistical significance cannot be guaranteed in advance; only the probability of detecting an effect of a specified magnitude can be planned.
