# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Core reproduction pipeline PASS / FROZEN. Phase 7 thesis analysis PASS / FROZEN. Phase 8 power planning PASS / FROZEN. Phase 9 confirmatory NEW-user cohort design PASS / FROZEN. Phase 10A synthetic hardware-saturation preflight is READY. No confirmatory-cohort LLM output has been observed yet.**

Active model used for the frozen experiments: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

## Frozen pilot workload and runtime
- pilot workload: 20 users, 94 continuous recommendation sessions
- 20 candidates/session; candidate seed 42
- Context Length 8192
- Evaluation Batch 512
- Physical Batch 256
- Max Concurrent 1 for the frozen pilot runs
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

Phase 9 made **zero LLM calls** and froze the confirmatory cohort before any new effectiveness outcome was observed.

Frozen confirmatory design:
- new users: **150**
- original pilot users excluded: **20**
- pilot overlap: **0**
- selected deterministic eligible-user ranks: **21 through 170**
- user-selection seed: `20260905`
- candidate size: **20**
- candidate seed: `42`
- recommendation sessions: **767**
- profile evidence events: **1,067**
- history length min/mean/max: **4 / 8.1133 / 35**
- required primary methods: **PURE and Recency-Focused**
- primary endpoint: **NDCG@10**, alpha 0.05 two-sided

Freeze identifiers:
- cohort manifest SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- sessions/candidates SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

Empirical compute estimate for required PURE + Recency-Focused scope:
- estimated LLM requests: **~3,676**
- estimated total reported tokens: **~3.48 million**
- estimated local inference time at the previous one-worker profile: **~3.34 hours**

Protocol: `docs/PHASE9_CONFIRMATORY_COHORT_PROTOCOL.md`.
Detailed result: `docs/PHASE9_CONFIRMATORY_COHORT_RESULTS.md`.
Authoritative local output: `outputs/phase9_confirmatory_cohort_v1/`.

## Phase 10A — Synthetic hardware-saturation preflight — READY

Purpose: determine whether **Max Concurrent Predictions = 2** can reduce Phase 10 wall-clock time without inspecting confirmatory outcomes.

Scientific isolation:
- synthetic prompts only;
- no confirmatory review/profile/candidate/target content is sent to the model;
- Phase 9 hashes are recomputed and verified before the benchmark;
- model, temperature, seed, context, batch sizes, GPU offload, Flash Attention and output schema remain unchanged.

Two-worker acceptance gates:
- exact canonical structured-output match for every sequential/concurrent probe pair;
- throughput speedup at least **1.15x**;
- no benchmark failure;
- peak VRAM at or below **97%** when `nvidia-smi` telemetry is available.

Before running the preflight, set only **LM Studio Max Concurrent Predictions = 2**. Keep all other accepted runtime settings unchanged. If the candidate fails, restore Max Concurrent to 1. If it passes, Phase 10B will be implemented with two workers only where dependencies permit; profile updates remain serial within each user.

Files:
- config: `config/phase10_hardware_preflight.toml`
- helpers: `src/pure_recommender/analysis/hardware_preflight.py`
- runner: `scripts/run_phase10_hardware_preflight.py`
- safe wrapper: `scripts/run_phase10_hardware_preflight_safe.py`
- tests: `tests/test_hardware_preflight.py`
- protocol: `docs/PHASE10_HARDWARE_PREFLIGHT_PROTOCOL.md`
- local output: `outputs/phase10_hardware_preflight_v1/`

## Scientific labeling
The frozen 20-user pilot remains the original reproduction result. The future 150-user confirmatory result, if executed, is a separate prospective evaluation and must be reported regardless of statistical significance. Runtime scheduling is selected before confirmatory outcomes are inspected and cannot be changed afterward based on NDCG.

## Next stage
Run the complete unit-test suite, then Phase 10A once. Review/freeze the concurrency decision. Only then build and run the Phase 10B confirmatory executor against the immutable Phase 9 manifests.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
