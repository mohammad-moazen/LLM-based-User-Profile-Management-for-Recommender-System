# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor is thesis-grade PASS / FROZEN. Phase 4 Profile Updater pilots v1-v3 have identified and hardened deletion/rewrite failure modes; pilot v4 is ready with an information-preserving directional overlap guard.**

Active model: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model results, not exact paper-checkpoint reproduction.

## Frozen Phase 1
- canonical interactions: 472,010
- selected users: 20
- frozen continuous recommendation sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

## Finalized runtime
- Context Length 8192
- GPU Offload 28/max
- CPU Thread Pool 7
- Evaluation Batch 512
- Physical Batch 256
- Max Concurrent 1
- Unified KV ON
- KV Cache GPU Offload ON
- Flash Attention ON
- K/V cache quantization OFF
- temperature 0.0 and seed 42 are sent explicitly by the current API experiments

## Phase 2 historical purchased-item baselines
- Sequential NDCG@1/5/10/20: 0.061667 / 0.182577 / 0.227799 / 0.366378
- Recency-Focused: 0.078333 / 0.199726 / 0.239947 / 0.378652
- ICL: 0.061667 / 0.186356 / 0.255724 / 0.371370

These remain historical results. Final thesis comparison should rerun compared methods under the finalized runtime/protocol.

## Phase 3 Review Extractor — PASS / FROZEN
Official downstream source:
`outputs/phase3_review_extractor_final_1024/`

Homogeneous final run:
- required/successful/failed: 134 / 134 / 0
- users: 20
- accepted likes/dislikes/key-features: 240 / 98 / 152
- accepted total: 490
- rejected unsupported/blank entries: 45
- total reported tokens: 97,350
- mean latency: 5.408 s
- temperature 0.0, seed 42, max output tokens 1024

Only profile-safe `extraction` strings from this artifact may feed Phase 4.

## Phase 4 Profile Updater
Paper behavior: concatenate previous profile with the new extracted likes/dislikes/key-features, then remove redundant/overlapping information while preserving crucial information. The exact JSON schema and deterministic post-processing are not published by the paper, so all safety constraints below are explicit reproduction choices.

### Pilot v1 — technical PASS / policy rejected
3/3 updates succeeded, but the model arbitrarily deleted unique non-conflicting evidence.

### Pilot v2 — incomplete / rejected
The stronger retention prompt still deleted unrelated unique evidence and one update failed because the model rewrote an input string rather than returning an exact allowed string.

### Pilot v3 — technical PASS / policy not frozen
ID-only structured output removed the string-rewrite failure mode. The model selected stable same-category IDs and a deterministic guard restored unsupported omissions.

Observed:
- 8/8 updates successful
- 0 failures
- 9 entries restored by guard
- 1 final removal
- 5,172 total reported tokens
- mean latency 1.612 s/update

The remaining defect was directional overlap handling: the one allowed removal deleted the richer sentence `Beautiful game. It has a lot of charm and it is challenging enough.` while retaining the shorter overlapping sentence `It has a lot of charm and it is challenging enough.` Merely detecting overlap was therefore insufficient.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V3.md`.

### Pilot v4 — READY
Keeps the successful v3 ID-only interface and adds an information-preserving dominance guard:
- unrelated unique omissions are restored;
- an omitted overlap can be removed only when a retained entry is strictly more informative;
- if the model selects a shorter overlap but omits the richer one, the richer entry is restored;
- a deterministic second pass then removes the dominated shorter representative;
- no profile text is generated or rewritten by the updater;
- exact duplicates still collapse safely.

Coverage is broadened to 3 deterministic eligible users × 5 chronological updates = 15 expected updates.

Configuration:
- source: final frozen Phase 3 extractor
- temperature 0.0
- seed 42
- max tokens 1024
- runtime 512 / 256 / 1
- output: `outputs/phase4_profile_updater_pilot_v4/`
- runner: `scripts/run_phase4_profile_updater_pilot_v4_safe.py`

## Next actions
1. Pull the branch and run the unit tests.
2. Run `python scripts/run_phase4_profile_updater_pilot_v4_safe.py` with LM Studio unchanged.
3. Audit all v4 guard restorations and final removals.
4. If v4 is technically clean and every final removal is information-preserving, freeze the updater policy and implement the full chronological profile-state cache for all required prefixes.
5. Implement the PURE recommender and evaluate the frozen 94 sessions.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
