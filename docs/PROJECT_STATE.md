# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Core reproduction pipeline PASS / FROZEN. Phase 7 thesis analysis PASS / FROZEN. Phase 8 power planning PASS / FROZEN. Phase 9 confirmatory NEW-user cohort design PASS / FROZEN. Phase 10 confirmatory study PASS / FROZEN.**

Active model: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

## Frozen confirmatory design

- 150 new users; original 20 pilot users excluded
- 767 frozen recommendation sessions
- 1,067 profile evidence/update events
- candidate size 20, candidate seed 42
- user-selection seed `20260905`
- primary comparison: **PURE vs Recency-Focused**
- primary endpoint: **user-level NDCG@10**
- primary test: **paired two-sided t-test**
- alpha: **0.05**
- cohort SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- session/candidate SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

## Phase 10A — Hardware preflight

Two-worker execution was faster (~2.15x) but failed the exact repeatability gate (5/8 exact matches), so confirmatory execution was frozen at **Max Concurrent Predictions = 1**. Other accepted runtime settings remained Context 8192, Evaluation Batch 512, Physical Batch 256, full GPU offload, Flash Attention ON.

## Phase 10B1 — Confirmatory Review Extractor — PASS / FROZEN

Authoritative local output:
`outputs/phase10_confirmatory_review_extractor_v1/`

- required / successful / failed: **1,067 / 1,067 / 0**
- users: **150**
- likes / dislikes / key features: **1,895 / 783 / 1,309**
- rejected unsupported entries: **263**
- prompt / completion / total tokens: **581,301 / 175,122 / 756,423**
- total LLM latency: **4,103.018 s**
- generation: temperature 0.0, max_tokens 1024, seed 42

Detailed result: `docs/PHASE10_CONFIRMATORY_REVIEW_EXTRACTOR_RESULTS.md`.

## Phase 10B2 — Confirmatory Profile Updater — PASS / FROZEN

Authoritative local output:
`outputs/phase10_confirmatory_profile_updater_v2/`

Final v2 completed all **1,067 / 1,067** profile updates for all **150** users with **0 unresolved failures**.

The earlier v1 artifact is audit-only. v2 used one uniform duplicate-ID canonicalization policy for exact repeated valid IDs, the accepted retention guard v4, and a conservative preserve-all fallback only when the frozen 8192-token runtime could not yield a usable updater state. Seven final profile states used this conservative fallback. The fallback preserves all distinct evidence and can reduce compaction only.

## Phase 10B3 — Confirmatory Recency-Focused — PASS / FROZEN

Authoritative local output:
`outputs/phase10_confirmatory_recency_v1/`

- successful sessions: **767 / 767**
- failed sessions: **0**
- users: **150**
- direct primary successes: **766**
- rank-map fallback successes: **1**
- generation: temperature 0.0, max_tokens 512, seed 42

Aggregate effectiveness was withheld from the handoff until PURE execution and Phase 10C.

## Phase 10B4 — Confirmatory PURE — EXECUTION COMPLETE WITH ONE UNRESOLVED STRUCTURAL OUTPUT

Authoritative local output:
`outputs/phase10_confirmatory_pure_v1/`

- valid model-ranked sessions: **766 / 767**
- unresolved sessions: **1**
- users represented: **150**
- direct primary successes: **756**
- rank-map fallback successes: **10**
- unresolved session: `A3C8IUK92R6137:13`

The unresolved session repeatedly produced a rank map with duplicate rank `20` and missing rank `13`. No malformed ranking was repaired.

Before confirmatory effectiveness metrics were inspected, the primary missing-output policy was frozen as a worst-case PURE contribution: **rank 20 / NDCG@10 = 0.0**. Sensitivity analyses also retain observed-only handling and an optimistic rank-1 bound.

## Phase 10C — Confirmatory Statistical Analysis — PASS / FROZEN

Detailed result:
`docs/PHASE10_CONFIRMATORY_RESULTS.md`

### User-equal NDCG

- Recency NDCG@10: **0.258760**
- PURE conservative primary NDCG@10: **0.322294**
- PURE observed-only NDCG@10: **0.322441**
- PURE optimistic-bound NDCG@10: **0.322597**

### Predeclared primary test

PURE minus Recency at user-level NDCG@10 across 150 confirmatory users:

- mean paired difference: **+0.063534**
- SD: **0.255705**
- SE: **0.020878**
- t(149): **3.0431**
- two-sided p-value: **0.002769**
- 95% CI: **[0.022278, 0.104790]**
- reject H0 at alpha 0.05: **YES**

Sensitivity conclusions are unchanged:

- observed-only p = **0.002716**, 95% CI **[0.022412, 0.104950]**
- optimistic rank-1 bound p = **0.002664**, 95% CI **[0.022552, 0.105122]**

## Scientific interpretation

Under the frozen prospective confirmatory protocol and this project's local derivative model/runtime, PURE achieved a higher mean user-level NDCG@10 than Recency-Focused in the 150-user confirmatory cohort, and the predeclared paired test rejected the null hypothesis of zero mean difference.

This is **not** an exact paper-checkpoint reproduction and should not be generalized as universal population superiority. The project differs from the paper in checkpoint, preprocessing/candidate-sampling implementation details, and prompt/schema engineering.

## Next stage

Phase 10 is complete. The next work should shift from model execution to thesis reporting: consolidate experimental methodology, pilot vs confirmatory separation, implementation deviations from the paper, confirmatory statistics, limitations, and final discussion/conclusion. No additional confirmatory users or repeated reruns should be added in pursuit of a different p-value.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
