# Phase 6 — Final Controlled Thesis Comparison

## Status

**PASS / FROZEN**

All four methods in the final comparison now have complete results on the same frozen workload and finalized runtime/generation controls.

## Common evaluation controls

- local derivative model: `llama-3.2-3b-instruct-uncensored`
- users: 20
- recommendation sessions: 94
- candidates/session: 20
- identical frozen candidate sets and candidate order across methods
- temperature: 0.0
- generation seed: 42
- max output tokens: 512
- primary serialization: direct complete numbered-candidate ranking
- fallback policy: at most one fresh rank-map request only after strict structural direct-parser failure
- malformed output repair: none
- NDCG aggregation: session scores averaged within user, then users averaged equally

The hybrid serialization policy is a reproduction engineering choice. Method semantics remain different: Sequential uses chronological purchases; Recency-Focused adds explicit emphasis on the latest purchase; ICL uses earlier purchases through `t-2` with the purchase at `t-1` as a demonstrated outcome; PURE additionally uses the frozen review-derived user profile.

## Final NDCG table

| Method | NDCG@1 | NDCG@5 | NDCG@10 | NDCG@20 |
|---|---:|---:|---:|---:|
| Sequential | 0.078333 | 0.191193 | 0.229859 | 0.373286 |
| Recency-Focused | 0.095000 | 0.206505 | 0.252952 | 0.385799 |
| ICL | 0.061667 | 0.184046 | 0.244447 | 0.368731 |
| **PURE** | **0.104251** | **0.243553** | **0.318376** | **0.416023** |

Exact PURE scores:

- NDCG@1: 0.10425070028011205
- NDCG@5: 0.24355349242822116
- NDCG@10: 0.3183764185292945
- NDCG@20: 0.4160225252419735

## Best baseline and PURE improvement

Recency-Focused is the strongest baseline at all four cutoffs in this final controlled local experiment.

| Metric | Best baseline (Recency) | PURE | Absolute gain | Relative gain |
|---|---:|---:|---:|---:|
| NDCG@1 | 0.095000 | 0.104251 | +0.009251 | +9.74% |
| NDCG@5 | 0.206505 | 0.243553 | +0.037048 | +17.94% |
| NDCG@10 | 0.252952 | 0.318376 | +0.065425 | +25.86% |
| NDCG@20 | 0.385799 | 0.416023 | +0.030223 | +7.83% |

## Interpretation for the thesis

Under this project's controlled 20-user / 94-session evaluation, PURE produces the highest NDCG at every reported cutoff. The largest relative gain over the strongest baseline occurs at NDCG@10 (+25.86%), while the smallest occurs at NDCG@20 (+7.83%). This pattern supports the project-level conclusion that the review-derived profile is most useful for improving the upper-middle portion of the ranked candidate list in this local experiment.

Recency-Focused consistently outperforms Sequential, indicating that explicitly emphasizing the latest observed purchase is useful for this model and frozen sample. ICL does not outperform Recency-Focused in the final controlled rerun and is below Sequential at NDCG@1, NDCG@5, and NDCG@20, although it exceeds Sequential at NDCG@10.

These observations must be reported as results of the local derivative model and frozen subset, not as exact reproduction of the paper's reported scores or checkpoint behavior.

## Authoritative result records

- PURE: `docs/PHASE5_PURE_RECOMMENDER_FINAL_RESULTS.md`
- Sequential: `docs/PHASE6_SEQUENTIAL_FINAL_RESULTS.md`
- Recency-Focused: `docs/PHASE6_RECENCY_FINAL_RESULTS.md`
- ICL: `docs/PHASE6_ICL_FINAL_RESULTS.md`

## Final project-level comparison result

For the final controlled thesis table, the method ordering by each reported cutoff is:

- NDCG@1: PURE > Recency-Focused > Sequential > ICL
- NDCG@5: PURE > Recency-Focused > Sequential > ICL
- NDCG@10: PURE > Recency-Focused > ICL > Sequential
- NDCG@20: PURE > Recency-Focused > Sequential > ICL
