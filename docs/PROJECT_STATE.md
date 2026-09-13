# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Core reproduction pipeline PASS / FROZEN. Phase 7 deterministic thesis analysis PASS / FROZEN. The project is now in thesis writing, interpretation, visualization, limitations, and optional-extension stage. No additional recommender-model run is required for the frozen core results.**

Active model used for the frozen experiments: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

## Frozen workload and runtime
- 20 users
- 94 continuous recommendation sessions
- 20 candidates/session
- frozen candidate order; candidate seed 42
- Context Length 8192
- Evaluation Batch 512
- Physical Batch 256
- Max Concurrent 1
- temperature 0.0 and generation seed 42 for final Phase 3/4/5/6 experiments
- max output tokens 512 for recommenders; 1024 for Review Extractor/Profile Updater

Temperature 0.0 plus seed 42 is recorded for reproducibility but is not treated as a guarantee of bit-for-bit identical LM Studio generation across separate executions.

## Phase 3 Review Extractor — PASS / FROZEN
Authoritative output: `outputs/phase3_review_extractor_final_1024/`

- required/successful/failed: 134 / 134 / 0
- accepted likes/dislikes/key-features: 240 / 98 / 152
- accepted total: 490
- rejected unsupported/blank entries: 45
- total tokens: 97,350
- mean latency: 5.408 s

## Phase 4 Profile Updater — PASS / FROZEN
Authoritative state artifact: `outputs/phase4_profile_updater_final_v4/profile_states.jsonl`

- users: 20
- expected/successful/failed updates: 134 / 134 / 0
- prefix contiguity: PASS
- guard restored/allowed removals: 619 / 11
- final raw/safe entries: 472 / 461
- final entry-count compaction: 2.331%
- total tokens: 161,457
- maximum prompt: 4,287 tokens
- mean/median latency: 3.050 / 1.728 s

For target position `t`, Phase 5 uses only profile state `(user_id, t-1)`.

## Phase 5 PURE Recommender — PASS / FROZEN
Authoritative output: `outputs/phase5_pure_recommender_hybrid_final_v4/`

Final hybrid mechanical-output policy:
- direct numbered ranking first;
- strict complete-permutation parser;
- one fresh rank-map fallback only after structural direct-parser failure;
- malformed direct response is not shown to fallback;
- no post-generation candidate repair.

Execution:
- requested/successful/failed: 94 / 94 / 0
- direct-primary successes: 93
- fallback attempts/successes: 1 / 1
- total requests: 95

Final PURE NDCG:
- NDCG@1: **0.10425070028011205**
- NDCG@5: **0.24355349242822116**
- NDCG@10: **0.3183764185292945**
- NDCG@20: **0.4160225252419735**

Detailed record: `docs/PHASE5_PURE_RECOMMENDER_FINAL_RESULTS.md`.

## Phase 6 — Final controlled baseline reruns — PASS / FROZEN
All final baselines use the same 94 frozen sessions, candidate sets/order, runtime/generation controls, strict direct ranking parser, one rank-map fallback only after structural direct failure, no repair, and the same equal-user NDCG aggregation.

### Sequential
- requested/successful/failed: 94 / 94 / 0
- NDCG@1/5/10/20: **0.078333 / 0.191193 / 0.229859 / 0.373286**
- detailed record: `docs/PHASE6_SEQUENTIAL_FINAL_RESULTS.md`

### Recency-Focused
- requested/successful/failed: 94 / 94 / 0
- NDCG@1/5/10/20: **0.095000 / 0.206505 / 0.252952 / 0.385799**
- detailed record: `docs/PHASE6_RECENCY_FINAL_RESULTS.md`

### ICL
- requested/successful/failed: 94 / 94 / 0
- NDCG@1/5/10/20: **0.061667 / 0.184046 / 0.244447 / 0.368731**
- detailed record: `docs/PHASE6_ICL_FINAL_RESULTS.md`

## Frozen final comparison

| Method | NDCG@1 | NDCG@5 | NDCG@10 | NDCG@20 |
|---|---:|---:|---:|---:|
| Sequential | 0.078333 | 0.191193 | 0.229859 | 0.373286 |
| Recency-Focused | 0.095000 | 0.206505 | 0.252952 | 0.385799 |
| ICL | 0.061667 | 0.184046 | 0.244447 | 0.368731 |
| **PURE** | **0.104251** | **0.243553** | **0.318376** | **0.416023** |

Recency-Focused is the strongest baseline at all four cutoffs. Relative PURE improvement over it is approximately:
- NDCG@1: +9.74%
- NDCG@5: +17.94%
- NDCG@10: +25.86%
- NDCG@20: +7.83%

Detailed record: `docs/PHASE6_FINAL_COMPARISON.md`.

## Phase 7 — Deterministic thesis analysis — PASS / FROZEN
Authoritative local output: `outputs/phase7_final_analysis_v1/`

Phase 7 makes **zero LLM calls** and analyzes the four frozen result sets only.

Validation:
- aligned sessions: 94
- users: 20
- user-level paired bootstrap repetitions: 10,000
- bootstrap seed: 20260913
- status: PASS

Scientific result:
- PURE has the highest observed NDCG point estimate at all four cutoffs.
- The largest relative improvement over the strongest baseline is at NDCG@10 (+25.86%).
- All 95% paired user-level bootstrap confidence intervals for PURE-minus-baseline include zero.
- Therefore the thesis must not claim conventional 95% statistical significance or population-level superiority from this 20-user subset.
- Bootstrap positive fractions are descriptive resampling quantities, not p-values.

Detailed frozen record: `docs/PHASE7_FINAL_ANALYSIS_RESULTS.md`.

Important local Phase 7 files:
- `outputs/phase7_final_analysis_v1/analysis_summary.json`
- `outputs/phase7_final_analysis_v1/analysis_report.md`
- `outputs/phase7_final_analysis_v1/paired_bootstrap.csv`
- `outputs/phase7_final_analysis_v1/final_comparison.svg`

## Scientific labeling
The final comparison and analysis are authoritative only for this project's local derivative model, frozen 20-user / 94-session subset, preprocessing policy, candidate sampling, prompts, structured-output validation, and reproduction engineering choices. They must not be presented as an exact reproduction of the paper checkpoint or full-dataset scores.

## Next stage
Proceed to thesis writing and presentation of results:
1. methodology/implementation chapter from the frozen protocol;
2. evaluation/results chapter using Phase 6 and Phase 7;
3. limitations and threats to validity;
4. comparison with the source paper without claiming exact reproduction;
5. optional ablation or second-dataset experiment only if explicitly desired.

No further core-model execution is required.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
