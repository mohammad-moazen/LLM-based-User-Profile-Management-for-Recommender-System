# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor PASS / FROZEN. Phase 4 Profile Updater PASS / FROZEN. Phase 5 still requires a final output policy: direct ranking failed on 2/94; same-seed corrective retry failed 0/2; scored pilot v2 passed 8/8 but was rejected because severe ties made candidate-order tie-breaking dominate; standalone rank-map pilot v3 is INCOMPLETE at 6/8. A uniform direct-primary + rank-map-fallback pilot v4 is READY.**

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

Shared reproduction choices across all Phase 5 output protocols:
- chronological purchased-item titles are prepended;
- profile categories come from the exact frozen Phase 4 state;
- frozen candidates are numbered 1..20 using titles; ASINs are hidden from the model;
- no target marker or future review is shown;
- temperature 0.0, seed 42, max tokens 512, and finalized runtime remain fixed;
- malformed model output is never silently repaired.

### Direct-ranking pilot v1 — PASS
6/6 pilot sessions succeeded. This established prompt/state alignment and ranking evaluation plumbing.

### Direct-ranking full attempt 1 — INCOMPLETE
- requested/successful/failed: 94 / 92 / 2
- provisional 92-session NDCG@1/5/10/20: 0.104435 / 0.247248 / 0.318287 / 0.416851
- failed sessions: `A3RQZ1J5F5G104:10`, `A26C4UAI3IXYF:6`
- both malformed outputs repeated candidate 20 and omitted another candidate despite `uniqueItems` in the requested schema.

The provisional metrics are not final.

### Formatting-only corrective retry — REJECTED
Result: 0/2 successful. Both malformed direct rankings were reproduced under the same deterministic retry policy, so same-seed corrective retry is not accepted.

### Scored-output pilot v2 — TECHNICAL PASS / FINAL POLICY REJECTED
- requested/successful/failed: 8 / 8 / 0
- known direct failures recovered structurally: 2 / 2
- diagnostic NDCG@1/5/10/20: 0.000000 / 0.265402 / 0.265402 / 0.390355
- sessions with score ties: 8 / 8
- total tie groups: 12
- candidates participating in tied groups: 152

The scored protocol was rejected for final use because frozen candidate-order tie-breaking determined too much of the ordering.

Detailed record: `docs/PHASE5_PURE_RECOMMENDER_SCORED_PILOT_V2.md`.

### Rank-map pilot v3 — INCOMPLETE / standalone policy rejected
Coverage: same 8 diagnostic sessions.

Result:
- requested/successful/failed: 8 / 6 / 2
- users represented among successful rows: 4
- known direct-ranking failures successful under rank-map: 2 / 2
- diagnostic six-row NDCG@1/5/10/20: 0.000000 / 0.354414 / 0.398940 / 0.430190
- mean/max prompt tokens on successful rows: 962 / 1,666
- mean completion tokens: 155.833
- mean latency: 3.768 s

Failed sessions:
- `A2GSRMMRODQ4JH:4`: duplicate rank 16, missing rank 19
- `A2GSRMMRODQ4JH:6`: duplicate rank 16, missing rank 3

The strict parser correctly rejected both responses. Thus rank-map does not solve the global uniqueness problem as a standalone serialization.

Important complementary observation:
- the direct primary protocol succeeds on these two rank-map failure cases;
- rank-map succeeds on both known direct-ranking failure cases.

Detailed record: `docs/PHASE5_PURE_RECOMMENDER_RANKMAP_PILOT_V3.md`.

## Phase 5 hybrid-output pilot v4 — READY
A single predefined conditional output policy is now under test for every session.

Policy:
1. issue the direct ranking-array request first;
2. validate it with the strict complete-permutation parser;
3. if and only if that model output is structurally invalid, discard it and issue one fresh rank-map request using the same frozen history, profile, candidates, model, temperature, seed, and token cap;
4. the invalid direct response is not shown to the fallback call;
5. accept the fallback only if the strict rank-map parser validates a complete permutation;
6. no candidate is inserted, removed, reordered, inferred, rescored, or otherwise repaired after generation;
7. API failures or unrelated validation failures do not silently trigger fallback.

This is a uniform conditional protocol applied to all sessions, not a manual patch for named failures.

Pilot coverage is the same eight-session diagnostic set. Acceptance criteria:
- 8/8 sessions successful;
- both known direct-ranking failures must be recovered by rank-map fallback;
- both known standalone rank-map failures must succeed through the direct primary path;
- no session may require post-generation repair;
- at most one fallback request is allowed per session.

Files:
- config: `config/phase5_pure_recommender_hybrid_pilot.toml`
- runner: `scripts/run_phase5_pure_recommender_hybrid_pilot.py`
- safe wrapper: `scripts/run_phase5_pure_recommender_hybrid_pilot_safe.py`
- output: `outputs/phase5_pure_recommender_hybrid_pilot_v4/`

If this pilot passes, the exact same conditional policy will be used in a clean all-94 run from scratch. Only a complete 94/94 run can become the final PURE metric artifact. Sequential, Recency, and ICL must then be rerun with the same final output policy for the thesis comparison table.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
