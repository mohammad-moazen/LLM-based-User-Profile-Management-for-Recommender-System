# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor is thesis-grade PASS / FROZEN with one clean homogeneous 134/134 run. Phase 4 Profile Updater pilots v1 and v2 were not accepted as final policy; pilot v3 is now configured with ID-only model selection plus a deterministic retention guard.**

The active model is the local derivative `llama-3.2-3b-instruct-uncensored`; LM Studio reports GGUF `Q8_0` (~3.84 GB). Results are local derivative-model results, not exact reproduction of the paper checkpoint.

## Environment
- Python + VS Code
- LM Studio / llama.cpp OpenAI-compatible server
- endpoint: `http://127.0.0.1:1234/v1`
- Intel i7-13700H, 32 GB RAM, RTX 4060 Laptop 8 GB VRAM
- workflow: ChatGPT pushes code/docs; user pulls/runs; runners publish compact results through `handoff/latest.json`
- do not overwrite the user's local uncommitted README changes

## Frozen Phase 1
- raw reviews: 497,577
- canonical interactions: 472,010
- final users: 55,209
- final items: 17,388
- eligible users: 54,451
- selected users: 20
- frozen continuous sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

Task: rank one ground-truth next item among 19 non-interacted negatives. NDCG is averaged within user across sessions, then across users.

## Finalized local runtime
- Context Length: 8192
- GPU Offload: 28 / max
- CPU Thread Pool: 7
- Evaluation Batch: 512
- Physical Batch: 256
- Max Concurrent: 1
- Unified KV: ON
- Context Checkpoints: 32
- KV Cache GPU Offload: ON
- Keep Model in Memory: ON
- mmap: ON
- Speculative Decoding: OFF
- Flash Attention: ON
- K/V Cache Quantization: OFF

100-request host-memory stability: PASS. Candidate `1024 / 512 / 1` was rejected because it was slower, used more RAM, and changed 2/12 sampled profile-safe outputs.

Current Phase 3/4 API requests explicitly use `temperature=0.0` and `seed=42`; LM Studio's Inference-tab temperature does not override those request values.

## Phase 2 purchased-item baselines — historical frozen
- Sequential NDCG@1/5/10/20: 0.061667 / 0.182577 / 0.227799 / 0.366378
- Recency-Focused: 0.078333 / 0.199726 / 0.239947 / 0.378652
- ICL: 0.061667 / 0.186356 / 0.255724 / 0.371370

Before the final thesis comparison table, rerun compared methods under the finalized runtime/protocol rather than overwriting these historical records.

## Phase 3 Review Extractor — PASS / FROZEN
Final source artifact:

`outputs/phase3_review_extractor_final_1024/`

Final result:
- required / successful / failed: 134 / 134 / 0
- users: 20
- likes: 240
- dislikes: 98
- key features: 152
- accepted entries: 490
- rejected unsupported/blank entries: 45
- total generated entries before filter: 535
- rejection rate: 8.41%
- prompt tokens: 74,956
- completion tokens: 22,394
- total tokens: 97,350
- total latency: 724.650 s (~12.08 min)
- mean latency: 5.408 s/extraction
- temperature: 0.0
- seed: 42
- max tokens: 1024
- status: PASS / FROZEN

Downstream Profile Updater consumes only accepted `extraction` objects from this final artifact.

Detailed final record: `docs/PHASE3_REVIEW_EXTRACTOR_FINAL_HOMOGENEOUS_RESULTS.md`.
Protocol: `docs/PHASE3_REVIEW_EXTRACTOR_PROTOCOL.md`.

## Phase 4 Profile Updater
Paper behavior: concatenate the previous profile with newly extracted likes/dislikes/key features, then remove redundant/overlapping information while preserving crucial information; paper prose also describes resolving conflicts to keep the profile compact and coherent.

Published updater prompt:
`You are given a list: {list}. Update this list by removing redundant or overlapping information. Note that crucial information should be preserved.`

### Pilot v1 — TECHNICAL PASS / POLICY NOT ACCEPTED
- 3/3 successful updates
- 0 technical failures
- 1,424 total tokens
- 2.840 s mean latency/update

The model deleted the unique like `Arrived even faster than i expected.` despite no obvious duplicate/overlap/conflict. Prompt-only compaction was therefore not accepted.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V1.md`.

### Pilot v2 — INCOMPLETE / POLICY NOT ACCEPTED
Pilot v2 strengthened the instruction to retain unique evidence and expanded coverage to 2 users × 4 updates.

Observed before fail-fast stop:
- successful updates: 4
- failed updates: 1
- successful-update tokens: 2,626
- mean successful-update latency: 2.856 s

Problems:
1. arbitrary unique deletion persisted. At the first user's update 2, both `Arrived even faster than i expected.` and `If you like really challenging games you should get it.` were omitted without mechanically defensible overlap with the retained like;
2. at the second user's first update, the model shortened a key-feature string, violating the exact-subset contract. The parser correctly rejected it.

One deletion was clearly defensible: `It has a lot of charm and it is challenging enough.` was overlapped by the retained longer string `Beautiful game. It has a lot of charm and it is challenging enough.`.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V2.md`.

### Pilot v3 — READY
Pilot v3 keeps the paper-derived chronological LLM update but hardens the interface:
- every concatenated entry receives a deterministic same-category ID (`L...`, `D...`, `K...`);
- the model returns IDs only, so it cannot rewrite evidence text;
- the dynamic JSON schema constrains each category to its own valid IDs;
- after model selection, a deterministic retention guard evaluates every omitted unique string;
- deletion is allowed only when a retained same-category string has exact/clear lexical overlap;
- otherwise the omitted unique entry is automatically restored;
- exact duplicate inputs collapse safely to one occurrence;
- all model selections, guard restorations, guard-allowed removals, and final removals are logged.

This guard is an explicit conservative reproduction choice because the paper does not publish its exact schema or deletion/conflict validator. Semantic conflicts without sufficient lexical overlap are preserved rather than risking unsupported information loss.

Pilot v3 coverage:
- deterministic 2 eligible users;
- first 4 chronological updates each;
- 8 expected updates total;
- temperature 0.0;
- seed 42;
- max tokens 1024;
- runtime 512 / 256 / 1;
- output: `outputs/phase4_profile_updater_pilot_v3/`.

Protocol: `docs/PHASE4_PROFILE_UPDATER_PROTOCOL.md`.

## Automatic experiment handoff
`handoff/latest.json` is a compact mailbox. Runners commit/push only that file and never README/unrelated local changes. Fatal wrappers publish traceback when possible.

## Next actions
1. Pull the branch.
2. Run the unit-test suite.
3. Keep LM Studio on finalized `512 / 256 / 1`.
4. Run `python scripts/run_phase4_profile_updater_pilot_safe.py`.
5. Review all 8 v3 updates, especially `guard_restored_entries` and final `removed_entries`.
6. If v3 is technically clean and final removals are mechanically defensible, freeze the Profile Updater policy and implement the full chronological state cache.
7. Implement PURE recommender and evaluate it on the frozen 94 sessions.
8. Rerun final comparison baselines under the finalized runtime/protocol.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
