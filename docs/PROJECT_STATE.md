# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Core reproduction pipeline PASS / FROZEN. Phase 7 thesis analysis PASS / FROZEN. Phase 8 power planning PASS / FROZEN. Phase 9 confirmatory NEW-user cohort design PASS / FROZEN. The next stage is preparation of a separate Phase 10 confirmatory executor that must consume the frozen Phase 9 manifests without reselecting users or candidates.**

Active model used for the frozen experiments: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

## Frozen pilot workload and runtime
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

## Phase 9 — Confirmatory NEW-user cohort design — PASS / FROZEN

Phase 9 made **zero LLM calls** and froze the confirmatory cohort before any new effectiveness outcome was observed.

Frozen confirmatory design:
- new users: **150**
- original pilot users excluded: **20**
- pilot overlap: **0**
- total eligible users in cleaned dataset: **54,451**
- selected eligible-user ranks: **21 through 170** under the frozen deterministic order
- user-selection seed: `20260905`
- candidate size: **20**
- candidate seed: `42`
- generated recommendation sessions: **767**
- profile evidence events: **1,067**
- history length min/mean/max: **4 / 8.1133 / 35**
- primary methods: **PURE and Recency-Focused**
- primary endpoint: **NDCG@10**, alpha 0.05 two-sided

Freeze identifiers:
- cohort manifest SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- sessions/candidates SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

Empirical compute estimate for the required primary scope (PURE + Recency-Focused):
- estimated LLM requests: **~3,676.16**
- estimated total reported tokens: **~3.48 million**
- estimated local inference time: **~3.34 hours**

Optional Sequential + ICL secondary scope adds roughly 1,534 requests and 0.52 hours; the full four-method estimate is ~5,210 requests and ~3.86 hours.

Protocol: `docs/PHASE9_CONFIRMATORY_COHORT_PROTOCOL.md`.
Detailed result: `docs/PHASE9_CONFIRMATORY_COHORT_RESULTS.md`.
Authoritative local output: `outputs/phase9_confirmatory_cohort_v1/`.

## Scientific labeling
The frozen 20-user pilot remains the original reproduction result. Phase 9 is a prospective design artifact only; it does not change the pilot's effectiveness conclusions. Any future 150-user confirmatory result must be reported separately and regardless of whether it reaches statistical significance.

## Next stage
Prepare Phase 10 as a separate confirmatory execution pipeline. Before the first Phase 10 model call, the executor must verify both Phase 9 SHA256 freeze identifiers, consume the frozen `cohort_users.json` and `sessions.jsonl.gz` directly, keep the model/prompt/runtime/output-validation protocols unchanged, and preserve the pre-declared primary test PURE vs Recency-Focused at NDCG@10. No user, session, candidate, endpoint, or analysis rule may be changed after inspecting confirmatory outcomes without declaring a new experiment version.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
