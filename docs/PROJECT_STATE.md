# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Core reproduction pipeline PASS / FROZEN. Phase 7 thesis analysis PASS / FROZEN. Phase 8 power planning PASS / FROZEN. Phase 9 confirmatory NEW-user cohort design PASS / FROZEN. Phase 10A hardware preflight COMPLETE. Phase 10B1 confirmatory Review Extractor PASS / FROZEN. Phase 10B2 v1 is ABANDONED / AUDIT-ONLY after a persistent duplicate-ID structural failure. Phase 10B2 v2 homogeneous restart is READY.**

Active model: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

## Frozen confirmatory design

- 150 new users; original 20 pilot users excluded
- 767 frozen recommendation sessions
- 1,067 profile evidence/update events
- candidate size 20, candidate seed 42
- user-selection seed `20260905`
- primary comparison: **PURE vs Recency-Focused**
- primary endpoint: **user-level NDCG@10**, alpha 0.05 two-sided
- cohort SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- session/candidate SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

No confirmatory recommendation outcome has been run or inspected yet.

## Phase 10A — Hardware preflight

Two-worker execution was faster (~2.15x) but failed the exact repeatability gate (5/8 exact matches), so confirmatory execution is frozen at **Max Concurrent Predictions = 1**. Other accepted runtime settings remain Context 8192, Evaluation Batch 512, Physical Batch 256, full GPU offload, Flash Attention ON.

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

## Phase 10B2 v1 — ABANDONED / AUDIT-ONLY

The first Profile Updater run produced 225 valid states, then repeatedly failed on task `A1WTMP0BQ76WTZ:12` because the model returned duplicate valid ID `D011` in the `dislikes` array. Three fresh retries and a `uniqueItems=true` schema hint still reproduced the same defect.

The 225 valid v1 states are preserved only for audit. They will **not** be reused in the final confirmatory Profile Updater artifact, avoiding a mixed-policy result.

## Phase 10B2 v2 — Homogeneous Profile Updater — READY

v2 restarts all **1,067** profile updates from the beginning under one uniform policy.

Unchanged components:
- accepted Phase 4 Profile Updater prompt;
- information-preserving retention guard v4;
- model and local runtime;
- temperature `0.0`;
- seed `42`;
- max output tokens `1024`;
- Max Concurrent Predictions `1`.

New narrowly scoped normalization:
- repeated occurrences of the **same valid selected ID within the same category** are canonicalized to one occurrence before the existing strict parser runs;
- this preserves the selected ID set exactly;
- unknown IDs, cross-category IDs, wrong keys, malformed JSON, invalid types, and guard failures still fail;
- non-canonicalizable failures may receive at most three fresh requests with the same frozen settings.

v2 output is isolated at:
`outputs/phase10_confirmatory_profile_updater_v2/`

Resume is allowed only from rows already marked with policy `exact_duplicate_id_canonicalization_v2`. v1 states are never imported.

Files:
- policy helper: `src/pure_recommender/phase10_profile_canonical_v2.py`
- runner: `scripts/run_phase10_confirmatory_profile_updater_v2_safe.py`
- tests: `tests/test_phase10_profile_canonical_v2.py`
- protocol: `docs/PHASE10_PROFILE_UPDATER_V2_PROTOCOL.md`

## Scientific labeling

The 20-user pilot remains the original reproduction result. The 150-user confirmatory study is separate and must be reported regardless of statistical significance. The duplicate-ID canonicalization policy was fixed before any confirmatory recommendation outcome was produced or inspected.

## Next stage

Keep LM Studio on the accepted one-worker settings. Pull the branch, run the full test suite, then run `scripts/run_phase10_confirmatory_profile_updater_v2_safe.py`. Freeze v2 only if all 1,067 updates succeed. Only after that prepare the confirmatory Recency-Focused and PURE recommenders.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
