# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor is now thesis-grade PASS / FROZEN with one clean homogeneous 134/134 run. Phase 4 Profile Updater pilot v1 is implemented and ready to run.**

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

Every required extraction was regenerated from scratch under the same final prompt/schema/parser, generation configuration, and finalized runtime.

Final result:
- required: 134
- successful: 134
- failed: 0
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

The 45 rejected entries are expected conservative-filter events and never enter downstream profile-safe data.

Downstream Profile Updater must consume only `extraction` objects from the final artifact. Historical v5 and the 133/134 512-token clean attempt remain audit/development artifacts only.

Detailed final record: `docs/PHASE3_REVIEW_EXTRACTOR_FINAL_HOMOGENEOUS_RESULTS.md`.
Protocol: `docs/PHASE3_REVIEW_EXTRACTOR_PROTOCOL.md`.

## Phase 4 Profile Updater — PILOT V1 READY
Paper behavior: concatenate previous profile with the newly extracted likes/dislikes/key features, then use Profile Updater to remove redundant/overlapping information while preserving crucial information.

Published paper updater prompt:
`You are given a list: {list}. Update this list by removing redundant or overlapping information. Note that crucial information should be preserved.`

Active reproduction choice: conservative subset-preserving updater.
- profile begins empty;
- update chronologically;
- only final frozen extractor evidence is input;
- structured output contains `likes`, `dislikes`, `key_features`;
- every returned string must be an exact member of the same-category concatenated input list;
- updater may remove redundant/overlapping/conflicting entries;
- no paraphrase, new text, outside knowledge, cross-category movement, duplicate output, or silent repair;
- parser fails unsupported output rather than admitting ungrounded profile text.

Pilot v1:
- deterministic first eligible user;
- first 3 chronological extraction updates;
- temperature 0.0;
- seed 42;
- max tokens 1024;
- runtime 512 / 256 / 1;
- output: `outputs/phase4_profile_updater_pilot_v1/`;
- handoff includes previous profile, incoming extraction, updated profile, counts, latency, and failures.

Implemented files:
- `src/pure_recommender/pure/profile_updater.py`
- `src/pure_recommender/phase4/config.py`
- `config/phase4_profile_updater_pilot.toml`
- `scripts/run_phase4_profile_updater_pilot.py`
- `scripts/run_phase4_profile_updater_pilot_safe.py`
- `tests/test_profile_updater.py`
- `docs/PHASE4_PROFILE_UPDATER_PROTOCOL.md`

## Automatic experiment handoff
`handoff/latest.json` is a compact mailbox. Runners commit/push only that file and never README/unrelated local changes. Fatal wrappers publish traceback when possible.

## Next actions
1. Pull the branch.
2. Run the unit-test suite.
3. Keep LM Studio on the finalized `512 / 256 / 1` profile.
4. Run `python scripts/run_phase4_profile_updater_pilot_safe.py`.
5. Review the 3 chronological profile updates from the handoff.
6. If pilot v1 is acceptable, implement/freeze the full chronological Profile Updater state cache for all required prefixes.
7. Implement PURE recommender and evaluate it on the frozen 94 sessions.
8. Rerun final comparison baselines under the finalized runtime/protocol.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
