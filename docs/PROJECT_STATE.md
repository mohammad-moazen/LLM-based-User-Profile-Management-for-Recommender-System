# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Phase 3 Review Extractor PASS / FROZEN. Phase 4 Profile Updater PASS / FROZEN. Phase 5 PURE Recommender PASS / FROZEN. Phase 6A Sequential PASS / FROZEN. Phase 6B Recency-Focused PASS / FROZEN. Phase 6C ICL PASS / FROZEN. Final controlled Sequential vs Recency-Focused vs ICL vs PURE comparison PASS / FROZEN. Phase 7 deterministic thesis analysis is READY.**

Active model: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

## Frozen workload and runtime
- 20 users, 94 continuous recommendation sessions
- 20 candidates/session, frozen candidate order, candidate seed 42
- Context Length 8192
- Evaluation Batch 512
- Physical Batch 256
- Max Concurrent 1
- temperature 0.0, generation seed 42 for final Phase 3/4/5/6 experiments
- max output tokens: 512 for recommenders; 1024 for Review Extractor/Profile Updater

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
- final compaction: 2.331%
- total tokens: 161,457
- maximum prompt: 4,287 tokens
- mean/median latency: 3.050 / 1.728 s

For target position `t`, Phase 5 uses only profile state `(user_id, t-1)`.

## Phase 5 PURE Recommender — PASS / FROZEN
Authoritative output: `outputs/phase5_pure_recommender_hybrid_final_v4/`

Final hybrid policy:
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

Final NDCG:
- NDCG@1: **0.10425070028011205**
- NDCG@5: **0.24355349242822116**
- NDCG@10: **0.3183764185292945**
- NDCG@20: **0.4160225252419735**

Detailed record: `docs/PHASE5_PURE_RECOMMENDER_FINAL_RESULTS.md`.

## Phase 6 — Final controlled baseline reruns
All final baselines use the same 94 frozen sessions, candidate sets/order, runtime/generation controls, strict direct ranking parser, one rank-map fallback only after structural direct failure, no repair, and the same user-level NDCG aggregation. Method semantics remain distinct.

### Phase 6A Sequential — PASS / FROZEN
Authoritative output: `outputs/phase6_sequential_hybrid_final_v1/`

- requested/successful/failed: 94 / 94 / 0
- direct-primary successes: 94
- fallback attempts: 0
- NDCG@1/5/10/20: **0.078333 / 0.191193 / 0.229859 / 0.373286**

Detailed record: `docs/PHASE6_SEQUENTIAL_FINAL_RESULTS.md`.

### Phase 6B Recency-Focused — PASS / FROZEN
Authoritative output: `outputs/phase6_recency_hybrid_final_v1/`

- requested/successful/failed: 94 / 94 / 0
- direct-primary successes: 94
- fallback attempts: 0
- NDCG@1/5/10/20: **0.095000 / 0.206505 / 0.252952 / 0.385799**
- total tokens: 64,703
- mean session latency: 1.7223 s

Detailed record: `docs/PHASE6_RECENCY_FINAL_RESULTS.md`.

### Phase 6C ICL — PASS / FROZEN
Authoritative output: `outputs/phase6_icl_hybrid_final_v1/`

- requested/successful/failed: 94 / 94 / 0
- direct-primary successes: 94
- fallback attempts: 0
- NDCG@1/5/10/20: **0.061667 / 0.184046 / 0.244447 / 0.368731**
- total tokens: 66,909
- mean session latency: 1.0671 s

Detailed record: `docs/PHASE6_ICL_FINAL_RESULTS.md`.

## Final controlled thesis comparison — PASS / FROZEN

| Method | NDCG@1 | NDCG@5 | NDCG@10 | NDCG@20 |
|---|---:|---:|---:|---:|
| Sequential | 0.078333 | 0.191193 | 0.229859 | 0.373286 |
| Recency-Focused | 0.095000 | 0.206505 | 0.252952 | 0.385799 |
| ICL | 0.061667 | 0.184046 | 0.244447 | 0.368731 |
| **PURE** | **0.104251** | **0.243553** | **0.318376** | **0.416023** |

Recency-Focused is the strongest baseline at all four cutoffs. Relative PURE improvement over that strongest baseline is approximately:
- NDCG@1: +9.74%
- NDCG@5: +17.94%
- NDCG@10: +25.86%
- NDCG@20: +7.83%

Final comparison record: `docs/PHASE6_FINAL_COMPARISON.md`.

## Phase 7 — Deterministic thesis analysis — READY

Phase 7 is post-hoc analysis only and makes **zero LLM calls**. It consumes the four authoritative local result directories above and fails loudly unless all methods contain the exact same 94 successful sessions and 20 users.

Analysis outputs:
- final comparison CSV;
- PURE absolute/relative improvements;
- per-user NDCG table;
- paired user-level bootstrap with 10,000 deterministic replicates;
- PURE user-level win/tie/loss counts;
- target-rank summaries;
- token/latency comparison;
- dependency-free SVG comparison chart;
- Persian Markdown analysis report;
- compact machine-readable summary.

Files:
- config: `config/phase7_final_analysis.toml`
- analysis helpers: `src/pure_recommender/analysis/final_results.py`
- runner: `scripts/run_phase7_final_analysis.py`
- safe wrapper: `scripts/run_phase7_final_analysis_safe.py`
- local output: `outputs/phase7_final_analysis_v1/`
- protocol: `docs/PHASE7_FINAL_ANALYSIS_PROTOCOL.md`

The bootstrap resamples users, not sessions, to match the project's equal-user evaluation aggregation. Its confidence intervals describe uncertainty within this frozen 20-user subset and must not be presented as proof of population-level significance.

## Scientific labeling
The final comparison is authoritative for this project's local derivative model, frozen 20-user subset, preprocessing policy, candidate sampling, and reproduction engineering choices. It must not be presented as an exact reproduction of the paper's checkpoint or full-dataset scores.

## Next stage
Run Phase 7 once. After its handoff is reviewed, use the generated tables/statistics/figure to draft the thesis evaluation/results chapter. No further LLM recommendation run is required unless a new ablation or extension is explicitly added.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
