# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Core reproduction pipeline PASS / FROZEN. Phase 7 thesis analysis PASS / FROZEN. Phase 8 power planning PASS / FROZEN. Phase 9 confirmatory NEW-user cohort design PASS / FROZEN. Phase 10A hardware preflight completed: the two-worker runtime was rejected on repeatability grounds. Phase 10B1 confirmatory Review Extractor is READY.**

Active model: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

## Frozen pilot workload and runtime
- pilot workload: 20 users, 94 continuous recommendation sessions
- 20 candidates/session; candidate seed 42
- Context Length 8192
- Evaluation Batch 512
- Physical Batch 256
- Max Concurrent Predictions 1
- temperature 0.0 and generation seed 42 for final Phase 3/4/5/6 experiments
- max output tokens 512 for recommenders; 1024 for Review Extractor/Profile Updater

## Frozen pilot results
- PURE NDCG@1/5/10/20: **0.104251 / 0.243553 / 0.318376 / 0.416023**
- Sequential: **0.078333 / 0.191193 / 0.229859 / 0.373286**
- Recency-Focused: **0.095000 / 0.206505 / 0.252952 / 0.385799**
- ICL: **0.061667 / 0.184046 / 0.244447 / 0.368731**

Phase 7 user-level paired bootstrap used 10,000 replicates over 20 users. PURE has the highest point estimate at all cutoffs, but all 95% paired bootstrap CIs include zero. No conventional 95% significance claim is made for the pilot.

## Phase 8 — Prospective power analysis — PASS / FROZEN

Pre-declared primary endpoint:
- **PURE vs Recency-Focused**
- **NDCG@10**
- alpha 0.05, two-sided
- target power 80%
- paired statistical unit: user

Pilot-informed effect:
- paired mean delta: **0.06542480125013969**
- paired SD: **0.2567801793599952**
- `d_z`: **0.25478914070862463**

Planning result:
- raw estimated N: **121**
- safety margin: **20%**
- practical target: **150 NEW users**

The original 20 pilot users are excluded from the confirmatory 150 and are not rerun for the confirmatory hypothesis test.

Protocol: `docs/PHASE8_POWER_ANALYSIS_PROTOCOL.md`.
Detailed result: `docs/PHASE8_POWER_ANALYSIS_RESULTS.md`.

## Phase 9 — Confirmatory NEW-user cohort design — PASS / FROZEN

Phase 9 made zero LLM calls and froze the confirmatory cohort before any new effectiveness outcome was observed.

Frozen design:
- new users: **150**
- pilot overlap: **0**
- selected deterministic eligible-user ranks: **21 through 170**
- user-selection seed: `20260905`
- candidate size: **20**
- candidate seed: `42`
- recommendation sessions: **767**
- profile evidence events: **1,067**
- history length min/mean/max: **4 / 8.1133 / 35**
- primary methods: **PURE and Recency-Focused**
- primary endpoint: **NDCG@10**, alpha 0.05 two-sided

Freeze identifiers:
- cohort manifest SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- sessions/candidates SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

Empirical one-worker estimate for required PURE + Recency-Focused scope:
- estimated LLM requests: **~3,676**
- estimated total reported tokens: **~3.48 million**
- estimated local inference time: **~3.34 hours**

Protocol: `docs/PHASE9_CONFIRMATORY_COHORT_PROTOCOL.md`.
Detailed result: `docs/PHASE9_CONFIRMATORY_COHORT_RESULTS.md`.
Authoritative local output: `outputs/phase9_confirmatory_cohort_v1/`.

## Phase 10A — Hardware saturation preflight — COMPLETE

The revised synthetic preflight completed successfully and made zero confirmatory-cohort LLM calls.

Measured two-worker candidate:
- probes: 8
- sequential wall time: **27.7429 s**
- two-worker wall time: **12.9188 s**
- throughput speedup: **2.1475x**
- exact sequential/concurrent structured-output matches: **5/8 (62.5%)**
- peak VRAM: **4463 / 8188 MiB (54.5%)**
- peak GPU utilization: **100%**
- mean sampled GPU utilization: **79.86%**
- peak temperature: **66 C**

Decision: **two workers REJECTED** because exact-output repeatability failed the pre-declared 100% gate. The confirmatory execution returns to **Max Concurrent Predictions = 1**. The speed gain is not used because runtime-dependent model-output changes would weaken the controlled comparison.

Detailed result: `docs/PHASE10_HARDWARE_PREFLIGHT_RESULTS.md`.
Protocol: `docs/PHASE10_HARDWARE_PREFLIGHT_PROTOCOL.md`.

## Phase 10 — Confirmatory execution

Protocol: `docs/PHASE10_CONFIRMATORY_EXECUTION_PROTOCOL.md`.

### Phase 10B1 — Review Extractor — READY

This is the first stage that will process the 150-user confirmatory cohort with the LLM.

Guards before the first call:
- recompute/verify both frozen Phase 9 SHA256 identifiers;
- require exactly 150 users and 767 frozen sessions;
- require exactly **1,067** historical Review Extractor tasks;
- consume the frozen Phase 9 sessions directly;
- no user/candidate regeneration;
- runtime Max Concurrent Predictions = **1**.

Generation remains frozen:
- temperature 0.0
- seed 42
- max output tokens 1024
- accepted evidence-backed JSON schema
- entry-level verbatim grounding filter

Interruption recovery is enabled with `resume=true`; successful extraction tasks are not rerun after a restart.

Files:
- config: `config/phase10_confirmatory_review_extractor.toml`
- guarded runner: `scripts/run_phase10_confirmatory_review_extractor_safe.py`
- local output: `outputs/phase10_confirmatory_review_extractor_v1/`

## Scientific labeling
The 20-user pilot remains the original reproduction result. The 150-user confirmatory result is a separate prospective evaluation and must be reported regardless of statistical significance. Runtime scheduling was selected before confirmatory effectiveness outputs were inspected.

## Next stage
Restore **LM Studio Max Concurrent Predictions = 1**, keep all other validated runtime settings unchanged, run the full unit-test suite, then execute Phase 10B1. Review/freeze its 1,067 extraction results before preparing the Profile Updater stage.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
