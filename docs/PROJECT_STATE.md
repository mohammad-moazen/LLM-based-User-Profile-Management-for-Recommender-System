# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Core reproduction pipeline PASS / FROZEN. Phase 7 thesis analysis PASS / FROZEN. Phase 8 power planning PASS / FROZEN. Phase 9 confirmatory NEW-user cohort design is READY. No new LLM output is generated in Phase 9; it freezes 150 new users and their sessions before any confirmatory model run.**

Active model used for the frozen experiments: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

## Frozen workload and runtime
- pilot workload: 20 users, 94 continuous recommendation sessions
- 20 candidates/session; candidate seed 42
- Context Length 8192
- Evaluation Batch 512
- Physical Batch 256
- Max Concurrent 1
- temperature 0.0 and generation seed 42 for final Phase 3/4/5/6 experiments
- max output tokens 512 for recommenders; 1024 for Review Extractor/Profile Updater

## Phase 3 Review Extractor — PASS / FROZEN
Authoritative output: `outputs/phase3_review_extractor_final_1024/`

- required/successful/failed: 134 / 134 / 0
- accepted likes/dislikes/key-features: 240 / 98 / 152
- rejected unsupported/blank entries: 45
- total tokens: 97,350
- mean latency: 5.408 s

## Phase 4 Profile Updater — PASS / FROZEN
Authoritative state artifact: `outputs/phase4_profile_updater_final_v4/profile_states.jsonl`

- users: 20
- expected/successful/failed updates: 134 / 134 / 0
- guard restored/allowed removals: 619 / 11
- final raw/safe entries: 472 / 461
- final entry-count compaction: 2.331%
- total tokens: 161,457

## Phase 5 PURE Recommender — PASS / FROZEN
Authoritative output: `outputs/phase5_pure_recommender_hybrid_final_v4/`

- requested/successful/failed: 94 / 94 / 0
- direct-primary successes: 93
- fallback attempts/successes: 1 / 1
- NDCG@1/5/10/20: **0.104251 / 0.243553 / 0.318376 / 0.416023**

Detailed record: `docs/PHASE5_PURE_RECOMMENDER_FINAL_RESULTS.md`.

## Phase 6 — Final controlled baselines — PASS / FROZEN

- Sequential: **0.078333 / 0.191193 / 0.229859 / 0.373286**
- Recency-Focused: **0.095000 / 0.206505 / 0.252952 / 0.385799**
- ICL: **0.061667 / 0.184046 / 0.244447 / 0.368731**

Recency-Focused is the strongest baseline at all four cutoffs.

## Phase 7 — Deterministic thesis analysis — PASS / FROZEN
Authoritative local output: `outputs/phase7_final_analysis_v1/`.

- aligned sessions: 94
- users: 20
- paired user-level bootstrap repetitions: 10,000
- PURE has the highest observed NDCG at all four cutoffs
- all 95% paired bootstrap CIs for PURE-minus-baseline include zero
- no conventional 95% statistical-significance claim is supported by the 20-user pilot

Detailed record: `docs/PHASE7_FINAL_ANALYSIS_RESULTS.md`.

## Phase 8 — Prospective power analysis — PASS / FROZEN (planning)

Pre-declared primary endpoint:
- **PURE vs Recency-Focused**
- **NDCG@10**
- alpha 0.05, two-sided
- target power 80%
- user-level paired design

Pilot-informed effect:
- paired mean delta: **0.06542480125013969**
- paired SD: **0.2567801793599952**
- `d_z`: **0.25478914070862463**

Planning result:
- raw estimated N: **121**
- safety margin: **20%**
- practical target: **150 NEW users**

The original 20 pilot users are not counted in the confirmatory 150 and are not rerun for the confirmatory test. Phase 8 is a planning estimate, not a guarantee of significance.

Protocol: `docs/PHASE8_POWER_ANALYSIS_PROTOCOL.md`.
Detailed result: `docs/PHASE8_POWER_ANALYSIS_RESULTS.md`.

## Phase 9 — Confirmatory NEW-user cohort design — READY

Purpose: freeze the confirmatory sampling frame and candidate sessions **before any new LLM outcome is observed**.

Frozen design intent:
- 150 new eligible users only;
- original 20 pilot users explicitly excluded;
- reuse Phase 1 user-selection seed `20260905`;
- verify the pilot is exactly the first 20 users under that deterministic ordering;
- select the next 150 eligible users;
- reuse candidate size 20 and candidate seed 42;
- generate every continuous next-item session after three observed interactions;
- full-history exclusion for all 19 negative candidates;
- primary confirmatory methods: PURE and Recency-Focused only;
- primary endpoint remains NDCG@10, alpha 0.05 two-sided;
- Sequential and ICL are optional secondary methods.

Phase 9 makes **zero LLM calls**. It writes local cohort/session manifests plus SHA256 freeze identifiers and an empirical compute/token estimate based on the accepted pilot runs.

Files:
- config: `config/phase9_confirmatory_cohort.toml`
- helpers: `src/pure_recommender/analysis/confirmatory_cohort.py`
- runner: `scripts/run_phase9_confirmatory_cohort_design.py`
- safe wrapper: `scripts/run_phase9_confirmatory_cohort_design_safe.py`
- tests: `tests/test_confirmatory_cohort.py`
- protocol: `docs/PHASE9_CONFIRMATORY_COHORT_PROTOCOL.md`
- local output: `outputs/phase9_confirmatory_cohort_v1/`

Acceptance requires exactly 150 new users, zero pilot overlap, valid deterministic sessions/candidates, written cohort/session hashes, and zero LLM calls.

## Scientific labeling
The frozen pilot comparison is authoritative only for this project's local derivative model, frozen 20-user / 94-session subset, preprocessing, candidate sampling, prompts, and engineering choices. A future 150-user confirmatory result must be reported separately and regardless of whether it reaches statistical significance.

## Next stage
Run Phase 9 once and review/freeze its user/session hashes and compute estimate. Only after Phase 9 is frozen should a separate confirmatory execution stage be prepared. The confirmatory executor must consume the frozen Phase 9 manifests and must not reselect users based on outcomes.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
