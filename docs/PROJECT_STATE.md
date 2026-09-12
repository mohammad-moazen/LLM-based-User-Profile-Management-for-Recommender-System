# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor is thesis-grade PASS / FROZEN. Phase 4 Profile Updater pilot v4 passed and is accepted for the full chronological state-cache run. Phase 4 is not frozen until the all-134 run passes.**

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
Paper behavior: concatenate previous profile with the new extracted likes/dislikes/key-features, then remove redundant/overlapping information while preserving crucial information. The exact JSON schema and deterministic post-processing are not published by the paper, so the project safeguards below are explicit reproduction choices.

### Accepted updater interface
- profile starts empty for each user;
- chronological, no-future-leakage updates;
- source is only the frozen Phase 3 extraction artifact;
- every entry receives a stable same-category ID (`L...`, `D...`, `K...`);
- LLM returns IDs only, so it cannot rewrite evidence text;
- dynamic structured output restricts the response to valid same-category IDs;
- a deterministic v4 information-preserving guard restores unsupported omissions;
- exact duplicates may collapse;
- an overlap deletion is allowed only if another same-category entry strictly dominates it in information content under the conservative lexical rule;
- a second pass removes a dominated shorter representative if a richer overlap is present;
- semantic conflicts that cannot be established mechanically are preserved rather than silently deleted.

### Pilot history
- v1: technical PASS, policy rejected because unique evidence was arbitrarily deleted.
- v2: incomplete/rejected because arbitrary deletion persisted and the model rewrote one evidence string.
- v3: technical PASS, but symmetric overlap guard allowed the richer sentence to be deleted in favor of a shorter overlap.

### Pilot v4 — PASS / accepted for full-scale validation
Coverage: 3 users × 5 chronological updates = 15 updates.

Result:
- successful/failed: 15 / 0
- guard-restored entries: 51
- final removed entries: 1
- total reported tokens: 11,781
- total latency: 26.368 s
- mean latency: 1.758 s/update

The only final unique overlap deletion was information-preserving:
- removed: `It has a lot of charm and it is challenging enough.`
- retained: `Beautiful game. It has a lot of charm and it is challenging enough.`

No unrelated unique evidence remained deleted after the v4 guard. The large number of restorations shows that the guard materially changes local-model deletion behavior; this must remain documented.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V4.md`.
Protocol: `docs/PHASE4_PROFILE_UPDATER_PROTOCOL.md`.

## Phase 4 full chronological run — READY
The accepted v4 policy is now wired into a full state-cache runner.

Source workload expected from frozen Phase 3:
- 20 users
- 134 required historical extraction/profile updates

Files:
- `config/phase4_profile_updater_full.toml`
- `scripts/run_phase4_profile_updater_full.py`
- `scripts/run_phase4_profile_updater_full_safe.py`

Output:
`outputs/phase4_profile_updater_final_v4/profile_states.jsonl`

The runner:
- validates each user's extraction positions form a contiguous prefix;
- applies the v4 updater sequentially from an empty profile;
- stores one profile state after every observed interaction;
- records guard restorations/removals, token usage, latency, maximum prompt-token usage, and diagnostic entry-count compaction;
- publishes only a compact summary/error payload through the Git handoff.

The state after interaction position `t` will later be used only for a recommendation target at position `t+1` or later, never for the same purchase's review.

Phase 4 freeze criteria:
- all 134 updates succeed;
- prefix-contiguity invariant passes;
- prompt size remains viable under Context Length 8192;
- no malformed/unsupported output enters the profile states;
- states cover every required prefix for all 94 frozen recommendation sessions.

Compression is measured, not forced. Entry-count compression in the full run is diagnostic; the final recommender will measure actual prompt-token size.

## Automatic experiment handoff
`handoff/latest.json` is a compact mailbox. Experiment runners commit/push only that path and never stage README or unrelated local changes.

## Next actions
1. Keep LM Studio on the finalized `512 / 256 / 1` runtime and Context Length 8192.
2. Pull the branch.
3. Run the unit tests.
4. Run `python scripts/run_phase4_profile_updater_full_safe.py`.
5. Review the full-run summary from the handoff.
6. If 134/134 passes and state invariants are satisfied, freeze Phase 4.
7. Implement the final PURE recommender, map each frozen session to its preceding profile state, and evaluate NDCG on all 94 sessions.
8. Rerun the comparison baselines under the finalized protocol for the thesis comparison table.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
