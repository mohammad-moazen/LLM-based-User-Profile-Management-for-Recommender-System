# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Phase 3 Review Extractor PASS / FROZEN. Phase 4 Profile Updater PASS / FROZEN. Phase 5 PURE Recommender PASS / FROZEN. Phase 6A Sequential PASS / FROZEN. Phase 6B Recency-Focused PASS / FROZEN. Phase 6C ICL is READY for the final controlled rerun.**

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

### Phase 6C ICL — READY
ICL keeps paper-aligned semantics:
- interactions through `t-2` are earlier purchase context;
- purchase at `t-1` is presented as the in-context demonstrated recommendation outcome;
- current frozen candidates are ranked;
- reviews, ratings, PURE profiles, target markers, and future information are excluded.

Files:
- config: `config/phase6_icl_hybrid.toml`
- direct prompt: existing `src/pure_recommender/baselines/icl.py`
- rank-map fallback: `src/pure_recommender/baselines/icl_rankmap.py`
- runner: `scripts/run_phase6_icl_hybrid.py`
- safe wrapper: `scripts/run_phase6_icl_hybrid_safe.py`
- output: `outputs/phase6_icl_hybrid_final_v1/`

Acceptance criteria:
- 94/94 valid final rankings;
- zero failures;
- every triggered fallback passes strict rank-map validation;
- no post-generation repair.

After ICL passes, freeze the final thesis comparison table: Sequential vs Recency-Focused vs ICL vs PURE.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
