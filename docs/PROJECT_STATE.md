# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor is thesis-grade PASS / FROZEN with one clean homogeneous 134/134 run. Phase 4 Profile Updater pilot v1 technically passed but its deletion policy was not accepted; pilot v2 is now configured with a retention-biased policy and broader qualitative coverage.**

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

Downstream Profile Updater consumes only accepted `extraction` objects from this final artifact. Historical v5 and the 133/134 512-token clean attempt remain audit/development artifacts only.

Detailed final record: `docs/PHASE3_REVIEW_EXTRACTOR_FINAL_HOMOGENEOUS_RESULTS.md`.
Protocol: `docs/PHASE3_REVIEW_EXTRACTOR_PROTOCOL.md`.

## Phase 4 Profile Updater
Paper behavior: concatenate the previous profile with newly extracted likes/dislikes/key features, then remove redundant/overlapping information while preserving crucial information; paper prose also describes resolving conflicts to keep the profile compact and coherent.

Published updater prompt:
`You are given a list: {list}. Update this list by removing redundant or overlapping information. Note that crucial information should be preserved.`

### Reproduction contract
- profile starts empty;
- updates are chronological and leakage-safe;
- only the final frozen extractor evidence is input;
- structured output contains `likes`, `dislikes`, `key_features`;
- every returned string must be an exact member of the same-category concatenated input;
- no paraphrase, new text, outside knowledge, cross-category movement, duplicate output, or silent repair;
- parser rejects unsupported output.

### Pilot v1 — TECHNICAL PASS / POLICY NOT ACCEPTED
Pilot v1 ran 3 chronological updates for user `A174LCVSHN24BT`:
- successful: 3/3
- failed: 0
- total tokens: 1,424
- mean latency: 2.840 s/update

Technical validation succeeded, but update 2 deleted the unique like `Arrived even faster than i expected.` even though it was neither a duplicate nor an obvious overlap/direct conflict. This showed that the generic compacting instruction could over-compress the profile beyond the paper-supported operation. Therefore v1 is not accepted for the full run.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V1.md`.

### Pilot v2 — READY
The exact-subset validator is retained, but the prompt is now retention-biased:
- retain unique evidence by default;
- remove only exact duplicates, clear redundancy/overlap, or clear direct conflicts;
- do not delete unique non-conflicting evidence merely because it seems less relevant or to shorten the profile;
- for clear overlap, keep the more specific/informative source string;
- for an unambiguous direct conflict, newer evidence may supersede older evidence; if uncertain, preserve both.

Pilot v2 coverage:
- deterministic 2 eligible users;
- first 4 chronological updates each;
- 8 expected updates total;
- temperature 0.0;
- seed 42;
- max tokens 1024;
- runtime 512 / 256 / 1;
- output: `outputs/phase4_profile_updater_pilot_v2/`.

The runner now publishes the exact concatenated profile, updated profile, and mechanically computed removed strings for every category/update so every deletion can be audited qualitatively.

Protocol: `docs/PHASE4_PROFILE_UPDATER_PROTOCOL.md`.

## Automatic experiment handoff
`handoff/latest.json` is a compact mailbox. Runners commit/push only that file and never README/unrelated local changes. Fatal wrappers publish traceback when possible.

## Next actions
1. Pull the branch.
2. Run the unit-test suite.
3. Keep LM Studio on finalized `512 / 256 / 1`.
4. Run `python scripts/run_phase4_profile_updater_pilot_safe.py`.
5. Review all 8 updates and every removed string from the handoff.
6. If pilot v2 removals are defensible and all updates pass, implement/freeze the full chronological Profile Updater state cache.
7. Implement PURE recommender and evaluate it on the frozen 94 sessions.
8. Rerun final comparison baselines under the finalized runtime/protocol.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
