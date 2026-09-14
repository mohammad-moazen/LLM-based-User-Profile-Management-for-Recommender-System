# Phase 10 — Confirmatory Results

## Status

**PASS / FROZEN**

This document records the prospective 150-user confirmatory study designed in Phases 8–9 and executed in Phase 10. The study is separate from the original 20-user pilot cohort.

## Frozen primary contract

- Comparison: **PURE vs Recency-Focused**
- Primary metric: **user-level NDCG@10**
- Statistical unit: **user**
- Test: **paired two-sided t-test**
- Alpha: **0.05**
- Confirmatory users: **150 new users**
- Frozen recommendation sessions: **767**
- Cohort SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- Session/candidate SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

The original 20-user pilot was excluded from the confirmatory hypothesis test.

## Execution completeness

### Recency-Focused

- successful sessions: **767 / 767**
- failed sessions: **0**
- users: **150**
- direct primary successes: **766**
- rank-map fallback successes: **1**

### PURE

- successful model-ranked sessions: **766 / 767**
- unresolved structural output sessions: **1**
- users represented: **150**
- direct primary successes: **756**
- rank-map fallback successes: **10**
- unresolved session: `A3C8IUK92R6137:13`

The unresolved PURE session repeatedly produced a structurally invalid rank map with duplicate rank `20` and missing rank `13`. No malformed ranking was repaired or outcome-selected.

## Pre-analysis missing-output policy

Before confirmatory effectiveness metrics were inspected, the unresolved PURE session was assigned a conservative primary contribution equivalent to **rank 20**, giving **NDCG@10 = 0.0**. This is a worst-case primary imputation for PURE and therefore cannot improve the primary result in PURE's favor.

Two sensitivity analyses were also retained:

1. observed-only handling of the unresolved session;
2. an optimistic rank-1 bound.

## User-equal aggregate NDCG

| Method | NDCG@1 | NDCG@5 | NDCG@10 | NDCG@20 |
|---|---:|---:|---:|---:|
| Recency-Focused | 0.077994 | 0.189828 | 0.258760 | 0.381475 |
| PURE — conservative primary | 0.094975 | 0.259431 | **0.322294** | 0.420701 |
| PURE — observed-only sensitivity | 0.095047 | 0.259568 | 0.322441 | 0.420797 |
| PURE — optimistic rank-1 bound | 0.095278 | 0.259734 | 0.322597 | 0.420935 |

## Primary confirmatory test

For the predeclared user-level NDCG@10 endpoint, the paired PURE-minus-Recency differences across all 150 confirmatory users were:

- mean difference: **+0.063534**
- SD of paired differences: **0.255705**
- standard error: **0.020878**
- t statistic: **3.0431**
- degrees of freedom: **149**
- two-sided p-value: **0.002769**
- 95% confidence interval: **[0.022278, 0.104790]**

Because the confidence interval is entirely above zero and `p < 0.05`, the predeclared null hypothesis of zero mean paired difference is rejected for this confirmatory cohort.

## Sensitivity analyses

### Observed-only

- mean difference: **+0.063681**
- p-value: **0.002716**
- 95% CI: **[0.022412, 0.104950]**

### Optimistic rank-1 bound

- mean difference: **+0.063837**
- p-value: **0.002664**
- 95% CI: **[0.022552, 0.105122]**

The inferential conclusion is unchanged across all three handling rules.

## Interpretation

Under the frozen prospective confirmatory protocol and this project's local derivative `llama-3.2-3b-instruct-uncensored` Q8_0 runtime, PURE achieved a higher mean user-level NDCG@10 than the Recency-Focused baseline in the 150-user confirmatory cohort. The primary paired test provides statistically significant evidence for a positive mean difference within this confirmatory design.

This should **not** be described as an exact reproduction of the paper checkpoint or as universal population superiority. The project differs from the paper in model checkpoint, preprocessing and candidate-sampling implementation details, and machine-readable prompt/schema engineering. The result is therefore a confirmatory result for this local derivative-model reproduction and its frozen cohort/protocol.

## Scientific safeguards retained

- original 20-user pilot excluded from the confirmatory test;
- confirmatory sample size fixed prospectively from Phase 8 planning;
- endpoint, test, alpha, statistical unit, cohort, sessions, candidates, and runtime were frozen before effectiveness results were inspected;
- no adding users after observing results;
- no malformed recommender output was deterministically repaired;
- the sole unresolved PURE session received a pre-analysis worst-case primary NDCG@10 contribution;
- result is reported regardless of direction/significance.

## Final label

**Phase 10 confirmatory study: PASS / FROZEN — primary endpoint favors PURE over Recency-Focused in this local derivative-model confirmatory cohort.**
