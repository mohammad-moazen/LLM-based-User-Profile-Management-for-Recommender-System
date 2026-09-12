# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor PASS / FROZEN. Phase 4 Profile Updater PASS / FROZEN after a clean 134/134 full run. Phase 5 PURE Recommender pilot v1 is implemented and ready.**

Active model: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB). Results are local derivative-model reproduction results, not exact paper-checkpoint reproduction.

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
- current Phase 3/4/5 API requests explicitly send temperature 0.0 and seed 42

## Phase 2 historical purchased-item baselines
- Sequential NDCG@1/5/10/20: 0.061667 / 0.182577 / 0.227799 / 0.366378
- Recency-Focused: 0.078333 / 0.199726 / 0.239947 / 0.378652
- ICL: 0.061667 / 0.186356 / 0.255724 / 0.371370

These remain historical records. Final thesis comparison must rerun compared methods under the finalized runtime/protocol rather than overwrite the historical artifacts.

## Phase 3 Review Extractor — PASS / FROZEN
Official downstream source:
`outputs/phase3_review_extractor_final_1024/`

Final homogeneous run:
- required/successful/failed: 134 / 134 / 0
- users: 20
- accepted likes/dislikes/key-features: 240 / 98 / 152
- accepted total: 490
- rejected unsupported/blank entries: 45
- total reported tokens: 97,350
- mean latency: 5.408 s
- temperature 0.0, seed 42, max output tokens 1024

Only accepted profile-safe `extraction` strings feed Phase 4.

## Phase 4 Profile Updater — PASS / FROZEN
Official state artifact:
`outputs/phase4_profile_updater_final_v4/profile_states.jsonl`

Frozen policy:
- profile starts empty per user;
- chronological/no-future-leakage updates;
- stable same-category IDs (`L...`, `D...`, `K...`);
- model returns IDs only and cannot rewrite evidence;
- deterministic information-preserving dominance guard restores unsupported omissions;
- exact duplicates may collapse;
- overlap removal is allowed only when another same-category entry is strictly richer under the conservative lexical rule;
- unresolved semantic conflicts are preserved rather than silently deleted.

Final full run:
- users: 20
- expected/successful/failed updates: 134 / 134 / 0
- prefix contiguity invariant: PASS
- guard-restored entries: 619
- guard-allowed removals: 11
- cumulative raw/safe prefix entries: 2,925 / 2,849
- cumulative entry-count compaction: 2.598%
- final raw/safe entries: 472 / 461
- final entry-count compaction: 2.331%
- prompt/completion/total tokens: 146,320 / 15,137 / 161,457
- maximum updater prompt: 4,287 tokens at `A3RQZ1J5F5G104:19`
- total latency: 408.766 s
- mean latency: 3.050 s/update
- median latency: 1.728 s/update
- status: PASS / FROZEN

Detailed record: `docs/PHASE4_PROFILE_UPDATER_FINAL_RESULTS.md`.

For a recommendation target at purchase position `t`, Phase 5 may use only the profile state after interaction position `t-1`.

## Phase 5 PURE Recommender — PILOT V1 READY
Paper Algorithm 1 defines the recommender as using the updated profile, purchased items, and next-purchase candidates. The paper's published prompt is:

`Positive aspects: {likes} Negative aspects: {dislikes} Key Features: {key features} Based on these inputs, rank the {candidate list} from 1 to 20 by evaluating their likelihood of being purchased.`

The paper does not show the exact serialization of purchased-item history in that template. This reproduction therefore prepends chronological purchased-item titles, then uses the published profile labels and frozen numbered candidate list. This is an explicit reproduction serialization choice.

Phase 5 invariants:
- target position `t` uses observed purchases `1..t-1`;
- profile state must be exactly `(user_id, t-1)`;
- frozen candidate set remains exactly 20 items;
- ASINs are hidden from the LLM and numbered candidate titles are used;
- structured JSON output requires a complete unique permutation of candidate numbers 1..20;
- strict parser maps numbers back to frozen ASINs;
- no malformed output, missing state, or future information is repaired silently.

Pilot v1:
- first 6 frozen sessions;
- temperature 0.0;
- seed 42;
- max tokens 512;
- output: `outputs/phase5_pure_recommender_pilot/`;
- runner: `scripts/run_phase5_pure_recommender_safe.py`.

Pilot NDCG is diagnostic only. Full reported PURE metrics require all 94 frozen sessions with the same user-level aggregation policy.

Protocol: `docs/PHASE5_PURE_RECOMMENDER_PROTOCOL.md`.

## Next actions
1. Keep LM Studio on finalized 512 / 256 / 1 and Context Length 8192.
2. Pull the branch and run the unit tests.
3. Run `python scripts/run_phase5_pure_recommender_safe.py`.
4. Review 6/6 state alignment, ranking validity, prompt size, and pilot NDCG.
5. If the pilot passes, switch Phase 5 to all 94 frozen sessions and freeze the final PURE result.
6. Rerun Sequential, Recency, and ICL comparison methods under the finalized runtime/output protocol for the final thesis comparison table.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
