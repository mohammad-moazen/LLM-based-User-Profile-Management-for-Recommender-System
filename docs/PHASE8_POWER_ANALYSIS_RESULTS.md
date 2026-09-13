# Phase 8 — Prospective Power Analysis Results

## Status

**PASS / FROZEN as a planning result**

Phase 8 makes zero LLM calls and does not modify or rerun the frozen 20-user experiment. It uses the Phase 7 per-user paired outcomes only to estimate the scale of a future independent confirmatory cohort.

## Pre-declared primary endpoint

- comparison: **PURE vs Recency-Focused**
- metric: **NDCG@10**
- alpha: **0.05**
- test direction: **two-sided**
- target power: **80%**
- pilot statistical unit: **user**
- pilot users: **20**

## Pilot-informed paired effect

For the primary endpoint:

- observed paired mean delta, PURE minus Recency-Focused: **0.06542480125013969**
- sample standard deviation of paired user-level deltas: **0.2567801793599952**
- paired standardized effect `d_z`: **0.25478914070862463**

The observed standardized effect is modest, so the 20-user pilot is underpowered for a conventional 95% significance claim.

## Sample-size planning result

Using the pre-declared two-sided normal approximation:

- raw estimated users required for 80% power: **121**
- explicit safety margin: **20%**
- raw estimate after 20% inflation: `121 × 1.20 = 145.2`
- practical rounded planning target: **150 users**

### Critical cohort interpretation

The Phase 8 protocol explicitly states that the original frozen 20 users are **not** part of the future confirmatory cohort. Therefore, under the current anti-p-hacking design, the practical target means:

> **150 NEW independent users**, excluding the original frozen 20.

It must not be interpreted as “130 new users plus the previous 20” unless the study design is deliberately changed and documented before any new outcomes are inspected. The current confirmatory design keeps pilot and confirmatory cohorts separate.

## Scientific interpretation

The number 150 is a **planning target**, not a promise that the future result will be statistically significant. The effect size and variance are estimated from only 20 pilot users and can change in an independent cohort. The confirmatory result must be reported whether significant or not.

The next confirmatory experiment, if performed, must keep the following fixed before seeing new outcomes:

1. the new-user selection rule and sample size;
2. the local model/checkpoint and runtime settings;
3. preprocessing and candidate construction;
4. Review Extractor and Profile Updater policies;
5. recommendation prompts and structured-output validation;
6. the primary comparison PURE vs Recency-Focused;
7. the primary endpoint NDCG@10;
8. two-sided alpha 0.05 and user-level paired analysis;
9. no adding users or rerunning users after inspecting significance.

## Relationship to the frozen thesis result

This planning analysis does not change Phase 7. The frozen 20-user result remains: PURE has the best observed point estimate, but the current paired bootstrap confidence intervals include zero. Phase 8 only quantifies a defensible scale for a separate future confirmatory evaluation.
