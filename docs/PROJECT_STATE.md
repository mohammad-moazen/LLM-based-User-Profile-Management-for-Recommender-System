# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Core reproduction pipeline PASS / FROZEN. Phase 7 deterministic thesis analysis PASS / FROZEN. Phase 8 prospective statistical power analysis is READY. No frozen result will be rerun or altered; Phase 8 is planning-only and uses the existing 20-user outcomes to size a future NEW-user confirmatory cohort.**

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
- `outputs/phase7_final_analysis_v1/per_user_ndcg.csv`
- `outputs/phase7_final_analysis_v1/paired_bootstrap.csv`
- `outputs/phase7_final_analysis_v1/final_comparison.svg`

## Phase 8 — Prospective statistical power analysis — READY

Purpose: estimate the size of a **future new-user confirmatory cohort** without rerunning or changing the frozen 20-user experiment.

Pre-declared primary planning endpoint:
- comparison: **PURE vs Recency-Focused**
- metric: **NDCG@10**
- alpha: **0.05, two-sided**
- target power: **80%**
- statistical unit: **user**

Phase 8 uses the paired user-level differences from `outputs/phase7_final_analysis_v1/per_user_ndcg.csv` to estimate `d_z`, approximate required sample sizes for 80%/90% power, a sensitivity curve, and a conservative practical target with a 20% safety margin.

Critical anti-p-hacking rule: any future confirmatory evaluation must use a deterministic cohort of **new users excluding the original 20**, freeze its sample size and protocol before outcomes are inspected, and report the result regardless of significance. The original frozen cohort must not be rerun until a desired p-value appears.

Files:
- config: `config/phase8_power_analysis.toml`
- analysis helpers: `src/pure_recommender/analysis/power_analysis.py`
- runner: `scripts/run_phase8_power_analysis.py`
- safe wrapper: `scripts/run_phase8_power_analysis_safe.py`
- tests: `tests/test_power_analysis.py`
- protocol: `docs/PHASE8_POWER_ANALYSIS_PROTOCOL.md`
- local output: `outputs/phase8_power_analysis_v1/`

Phase 8 makes **zero LLM calls**.

## Scientific labeling
The frozen comparison and analysis are authoritative only for this project's local derivative model, frozen 20-user / 94-session subset, preprocessing policy, candidate sampling, prompts, structured-output validation, and reproduction engineering choices. They must not be presented as an exact reproduction of the paper checkpoint or full-dataset scores.

A Phase 8 sample-size estimate is itself uncertain because it is derived from a small pilot. It must be described as a planning estimate, never as a guarantee that a future cohort will be statistically significant.

## Next stage
1. Run the full unit-test suite.
2. Run `python scripts/run_phase8_power_analysis_safe.py`.
3. Review the Phase 8 handoff and freeze the planning estimate.
4. Only after the sample-size plan is frozen, decide whether to execute a separate new-user confirmatory expansion.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
