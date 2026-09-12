# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines remain historical records. Phase 3 Review Extractor PASS / FROZEN. Phase 4 Profile Updater PASS / FROZEN. Phase 5 PURE Recommender PASS / FROZEN after a clean 94/94 hybrid-output run. Phase 6 controlled final baseline reruns have started; Sequential is READY.**

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
- final Phase 3/4/5 and Phase 6 API experiments explicitly send temperature 0.0 and seed 42

Temperature 0.0 plus seed 42 is recorded for reproducibility but is not treated as a guarantee of bit-for-bit identical generation across separate LM Studio executions.

## Phase 2 historical purchased-item baselines
Historical results preserved from the earlier protocol:

- Sequential NDCG@1/5/10/20: 0.061667 / 0.182577 / 0.227799 / 0.366378
- Recency-Focused: 0.078333 / 0.199726 / 0.239947 / 0.378652
- ICL: 0.061667 / 0.186356 / 0.255724 / 0.371370

These remain historical records only. The final thesis comparison reruns each method under the finalized runtime/generation settings and final hybrid output-validation policy. Historical artifacts are not overwritten.

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

Only accepted profile-safe extraction strings feed Phase 4.

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

## Phase 5 PURE Recommender — PASS / FROZEN
The final accepted policy is the hybrid direct-primary + rank-map-fallback protocol.

Uniform policy for every session:
1. issue the direct ranking-array request;
2. validate with the strict complete-permutation parser;
3. only on structural direct-parser failure, discard that malformed output and issue one fresh rank-map request from the same frozen history/profile/candidates;
4. do not show the malformed primary response to the fallback;
5. permit at most one fallback request per session;
6. require the fallback to pass strict rank-map validation;
7. never repair candidates post-generation;
8. API or unrelated validation failures do not silently trigger fallback.

This is an explicit reproduction engineering choice because the paper does not publish an exact machine-readable output schema.

### Final hybrid full v4
Authoritative local output: `outputs/phase5_pure_recommender_hybrid_final_v4/`

- requested/successful/failed sessions: 94 / 94 / 0
- users: 20
- direct-primary successes: 93
- fallback attempts/successes: 1 / 1
- total LLM requests: 95
- fallback session: `A26C4UAI3IXYF:6`
- fallback direct error: `Ranking contains duplicate candidate numbers`
- fallback target rank: 9
- status: **PASS / FROZEN**

Final NDCG:
- NDCG@1: **0.10425070028011205**
- NDCG@5: **0.24355349242822116**
- NDCG@10: **0.3183764185292945**
- NDCG@20: **0.4160225252419735**

Usage/latency:
- prompt/completion/total tokens: 101,887 / 6,938 / 108,825
- mean/max prompt tokens per request: 1,072.495 / 2,801
- total request latency: 205.935 s
- mean request latency: 2.168 s
- mean/median session latency: 2.191 / 2.028 s

Detailed record: `docs/PHASE5_PURE_RECOMMENDER_FINAL_RESULTS.md`.

## Phase 6 — Final controlled baseline reruns
Goal: build the thesis-grade comparison table only after Sequential, Recency-Focused, and ICL are rerun on the same 94 sessions under the same finalized runtime/generation controls and the same hybrid mechanical output policy used by final PURE.

Shared final comparison controls:
- same 20 users and 94 frozen sessions;
- same 20 frozen candidates and candidate order;
- temperature 0.0;
- seed 42;
- max output tokens 512;
- direct structured ranking request first;
- one fresh rank-map fallback only after strict direct structural failure;
- no malformed output repair;
- same user-level NDCG aggregation.

Method semantics remain distinct and paper-aligned: the shared hybrid policy changes only machine-readable serialization/validation, not what information each recommender sees.

Protocol: `docs/PHASE6_FINAL_BASELINE_RERUN_PROTOCOL.md`.

### Phase 6A Sequential — READY
Sequential still sees only chronological purchased-item titles and frozen candidate titles. Reviews, ratings, PURE profiles, future information, and target markers are excluded.

Files:
- config: `config/phase6_sequential_hybrid.toml`
- direct prompt: existing `src/pure_recommender/baselines/sequential.py`
- rank-map fallback prompt: `src/pure_recommender/baselines/sequential_rankmap.py`
- runner: `scripts/run_phase6_sequential_hybrid.py`
- safe wrapper: `scripts/run_phase6_sequential_hybrid_safe.py`
- output: `outputs/phase6_sequential_hybrid_final_v1/`

Acceptance criteria:
- exactly 94 sessions attempted;
- 94/94 valid final rankings;
- zero failures;
- any triggered fallback succeeds under strict rank-map validation;
- no post-generation repair;
- final NDCG and protocol path counts recorded.

## Next actions
1. Keep LM Studio on finalized 512 / 256 / 1 and Context Length 8192.
2. Pull the branch and run the unit tests.
3. Run `python scripts/run_phase6_sequential_hybrid_safe.py`.
4. Review/freeze the new Sequential result.
5. Prepare and run Recency-Focused under the same controls.
6. Prepare and run ICL under the same controls.
7. Freeze the final thesis comparison table only after all three baseline reruns pass.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
