# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor PASS / FROZEN. Phase 4 Profile Updater PASS / FROZEN. Phase 5 hybrid-output pilot v4 produced valid final rankings for 8/8 diagnostic sessions and is accepted for a clean 94-session full validation. Phase 5 is not frozen until that all-94 run passes.**

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
- current Phase 3/4/5 API experiments explicitly send temperature 0.0 and seed 42

## Phase 2 historical purchased-item baselines
- Sequential NDCG@1/5/10/20: 0.061667 / 0.182577 / 0.227799 / 0.366378
- Recency-Focused: 0.078333 / 0.199726 / 0.239947 / 0.378652
- ICL: 0.061667 / 0.186356 / 0.255724 / 0.371370

These remain historical records. Final thesis comparison must rerun compared methods under the finalized runtime and final adopted output policy rather than overwrite historical artifacts.

## Phase 3 Review Extractor — PASS / FROZEN
Official source: `outputs/phase3_review_extractor_final_1024/`

Final homogeneous run:
- required/successful/failed: 134 / 134 / 0
- users: 20
- accepted likes/dislikes/key-features: 240 / 98 / 152
- accepted total: 490
- rejected unsupported/blank entries: 45
- total reported tokens: 97,350
- mean latency: 5.408 s
- temperature 0.0, seed 42, max output tokens 1024

## Phase 4 Profile Updater — PASS / FROZEN
Official state artifact: `outputs/phase4_profile_updater_final_v4/profile_states.jsonl`

Frozen policy:
- profile starts empty per user;
- chronological/no-future-leakage updates;
- model returns stable same-category evidence IDs only;
- deterministic information-preserving dominance guard restores unsupported omissions;
- exact duplicates may collapse;
- overlap removal is allowed only when a same-category entry is strictly richer under the conservative lexical rule;
- unresolved semantic conflicts are preserved.

Final full run:
- users: 20
- expected/successful/failed updates: 134 / 134 / 0
- prefix contiguity: PASS
- guard restored/allowed removals: 619 / 11
- final raw/safe entries: 472 / 461
- final entry-count compaction: 2.331%
- prompt/completion/total tokens: 146,320 / 15,137 / 161,457
- maximum updater prompt: 4,287 tokens
- mean/median latency: 3.050 / 1.728 s
- status: PASS / FROZEN

For recommendation target position `t`, Phase 5 uses only profile state `(user_id, t-1)`.

## Phase 5 PURE Recommender
Paper behavior is preserved: updated profile + purchased items + 20 next-purchase candidates. The paper does not publish an exact machine-readable output schema or exact purchased-item serialization.

Shared reproduction choices:
- chronological purchased-item titles are prepended;
- profile categories come from the exact frozen Phase 4 state;
- frozen candidates are numbered 1..20 using titles; ASINs are hidden from the model;
- no target marker or future review is shown;
- temperature 0.0, seed 42, max tokens 512, and finalized runtime remain fixed;
- malformed model output is never silently repaired.

### Direct-ranking full attempt 1 — INCOMPLETE
- requested/successful/failed: 94 / 92 / 2
- provisional 92-session NDCG@1/5/10/20: 0.104435 / 0.247248 / 0.318287 / 0.416851
- failed sessions: `A3RQZ1J5F5G104:10`, `A26C4UAI3IXYF:6`
- both malformed outputs repeated candidate 20 and omitted another candidate despite the requested uniqueness constraint.

### Formatting-only retry — REJECTED
A same-seed corrective retry failed 0/2 and reproduced the malformed pattern, so this is not accepted as a recovery policy.

### Scored-output pilot v2 — STRUCTURAL PASS / FINAL POLICY REJECTED
8/8 succeeded structurally, including both direct failures, but all 8 sessions contained score ties and 152 candidate participations occurred in tied groups. Frozen candidate-order tie-breaking therefore determined too much of the ranking.

### Standalone rank-map pilot v3 — INCOMPLETE / REJECTED AS STANDALONE
- requested/successful/failed: 8 / 6 / 2
- both historical direct failures succeeded under rank-map
- two other sessions failed because rank 16 was duplicated and another rank was missing.

The direct and rank-map serializations therefore showed complementary failure behavior.

### Hybrid-output pilot v4 — ACCEPTED FOR FULL VALIDATION
Uniform policy for every session:
1. issue the direct ranking-array request first;
2. validate with the strict complete-permutation parser;
3. only on a structural direct parser failure, discard the invalid response and issue one fresh rank-map request with the same frozen inputs/settings;
4. do not show the invalid primary response to the fallback;
5. allow at most one fallback request;
6. require the fallback to pass the strict rank-map parser;
7. never perform post-generation candidate repair.

Observed pilot result:
- requested/successful/failed: 8 / 8 / 0
- direct-primary successes: 7
- fallback attempts/successes: 1 / 1
- both historical standalone rank-map failures succeeded on the direct-primary path
- `A26C4UAI3IXYF:6` failed direct and was recovered by rank-map fallback
- `A3RQZ1J5F5G104:10`, which had failed direct in the earlier full run, produced a valid direct ranking in this rerun
- diagnostic NDCG@1/5/10/20: 0.000000 / 0.123630 / 0.236517 / 0.313679

The runner's historical handoff emitted `INCOMPLETE` only because its pilot-specific acceptance counter incorrectly required both previously known direct-failure IDs to fail direct again and be counted as fallback recoveries. That is not an invariant of the hybrid policy. All 8 sessions actually ended with valid strict-parser rankings, and every fallback that was triggered succeeded. Detailed record: `docs/PHASE5_PURE_RECOMMENDER_HYBRID_PILOT_V4.md`.

The differing direct outcome for `A3RQZ1J5F5G104:10` across separate executions also means temperature 0.0 plus seed 42 on the local backend must not be treated as a guarantee of bit-for-bit identical generation. Actual protocol path is recorded per session.

## Phase 5 hybrid full v4 — READY
The full runner applies the same hybrid policy uniformly to all 94 frozen sessions from scratch.

Files:
- config: `config/phase5_pure_recommender_hybrid_full.toml`
- runner: `scripts/run_phase5_pure_recommender_hybrid_full.py`
- safe wrapper: `scripts/run_phase5_pure_recommender_hybrid_full_safe.py`
- output: `outputs/phase5_pure_recommender_hybrid_final_v4/`

Final PASS criteria:
- exactly 94 frozen sessions attempted;
- all 94 finish with a valid complete ranking;
- zero session failures;
- direct structural failures may trigger at most one fresh rank-map fallback;
- any fallback parser failure makes the session fail;
- no post-generation candidate repair is permitted.

If the full run passes 94/94, freeze Phase 5 and record final PURE NDCG. Then rerun Sequential, Recency, and ICL under the same finalized runtime and output policy for the thesis comparison table.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
