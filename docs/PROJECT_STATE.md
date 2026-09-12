# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 PASS / FROZEN. Local LLM/runtime finalized. Phase 2 purchased-item baselines are historical PASS / FROZEN. Phase 3 Review Extractor PASS / FROZEN. Phase 4 Profile Updater PASS / FROZEN. Phase 5 direct-ranking pilot v1 PASS, but full attempt 1 is INCOMPLETE at 92/94. A same-seed formatting-only retry failed 0/2, so direct-permutation recovery is rejected and a score-based serialization pilot v2 is ready.**

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

These remain historical records. Final thesis comparison must rerun compared methods under the finalized runtime and the final adopted output protocol rather than overwrite the historical artifacts.

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

For a recommendation target at purchase position `t`, Phase 5 uses only the profile state after interaction position `t-1`.

## Phase 5 PURE Recommender
Paper Algorithm 1 defines the recommender as using the updated profile, purchased items, and next-purchase candidates. The paper's published prompt exposes positive aspects, negative aspects, key features, and asks for a ranking of 20 candidates. The paper does not publish the exact machine-readable output schema or purchased-item serialization.

Shared reproduction choices retained across Phase 5 protocols:
- chronological purchased-item titles are prepended;
- profile categories are serialized from the exact frozen Phase 4 state;
- frozen candidates are shown as numbered titles 1..20;
- ASINs remain hidden from the model;
- target position `t` uses profile state exactly `(user_id, t-1)`;
- no future review or target marker is shown;
- temperature 0.0, seed 42, max tokens 512, and finalized runtime remain fixed.

### Direct-ranking pilot v1 — PASS
- frozen sessions available: 94
- requested/successful/failed: 6 / 6 / 0
- users represented: 2
- state alignment: exact `target_position - 1`
- mean/max prompt tokens: 651.67 / 851
- mean completion tokens: 72
- total/mean latency: 11.709 s / 1.951 s
- diagnostic NDCG@1/5/10/20: 0.000000 / 0.000000 / 0.119783 / 0.274854
- status: PASS

Pilot metrics are diagnostic only. Detailed record: `docs/PHASE5_PURE_RECOMMENDER_PILOT_V1.md`.

### Direct-ranking full attempt 1 — INCOMPLETE
- requested sessions: 94
- successful sessions: 92
- failed sessions: 2
- users represented among successful sessions: 20
- prompt tokens: 98,825 total; 1,074.185 mean; 2,801 max
- completion tokens: 6,639 total; 72.163 mean
- latency: 196.672 s total; 2.138 s mean
- provisional 92-session NDCG@1/5/10/20: 0.104435 / 0.247248 / 0.318287 / 0.416851
- status: INCOMPLETE

The provisional NDCG values are not final because two sessions are absent.

Failed sessions:
- `A3RQZ1J5F5G104:10`
- `A26C4UAI3IXYF:6`

Both responses contained 20 numbers but duplicated candidate 20 and omitted another candidate. The local serving backend therefore did not fully enforce the requested JSON Schema `uniqueItems` property. The strict parser rejected both responses, and no malformed output entered evaluation.

Detailed record: `docs/PHASE5_PURE_RECOMMENDER_FULL_ATTEMPT1.md`.

### Formatting-only corrective retry — REJECTED
The diagnostic tested one corrective retry for each failed row with the same frozen inputs, model, temperature, seed, token cap, and direct-ranking schema. The previous malformed response was supplied and the model was asked only to correct the permutation format.

Result:
- rows tested: 2
- successful retries: 0
- failed retries: 2
- deterministic post-generation repair: none
- status: INCOMPLETE / retry policy rejected

For both sessions the retry reproduced the same malformed ranking. Repeating the same deterministic retry policy is therefore not accepted as a recovery mechanism.

Detailed record: `docs/PHASE5_MALFORMED_RANKING_RETRY_DIAGNOSTIC.md`.

## Phase 5 scored-output pilot v2 — READY
The recommendation objective and frozen inputs remain unchanged. Only machine-readable output serialization changes.

Protocol:
- the model emits one integer purchase-likelihood score in `[0, 1000]` for every candidate number 1..20;
- the JSON schema requires all 20 candidate-number keys explicitly and forbids missing/extra keys;
- ranking is derived by descending model score;
- exact score ties are broken by frozen candidate number ascending;
- the frozen candidate order was already randomized in Phase 1, so this tie rule is deterministic and does not use target information;
- no candidate score is inserted, inferred, rewritten, or repaired after generation;
- this is an explicit reproduction engineering choice because the paper does not publish an output schema.

Pilot coverage:
- original six successful Phase 5 pilot sessions;
- both direct-ranking full-run failures;
- 8 sessions total.

Files:
- implementation: `src/pure_recommender/pure/recommender_scores.py`
- config: `config/phase5_pure_recommender_scored_pilot.toml`
- runner: `scripts/run_phase5_pure_recommender_scored_pilot.py`
- safe wrapper: `scripts/run_phase5_pure_recommender_scored_pilot_safe.py`
- tests: `tests/test_pure_recommender_scores.py`
- output: `outputs/phase5_pure_recommender_scored_pilot_v2/`

Acceptance criteria:
- 8/8 sessions successful;
- both known direct-ranking failure sessions successful;
- all responses contain exactly 20 required score keys;
- derived ranking is a complete 20-candidate permutation;
- tie frequency is recorded for audit;
- no post-generation semantic or structural repair is used.

If this pilot passes, all 94 sessions will be rerun from scratch under the scored protocol. Only that homogeneous 94/94 run can become the final PURE metric artifact. The comparison baselines will then be rerun with the same final output serialization for the thesis table.

## Next actions
1. Keep LM Studio on finalized 512 / 256 / 1 and Context Length 8192.
2. Pull the branch and run unit tests.
3. Run `python scripts/run_phase5_pure_recommender_scored_pilot_safe.py`.
4. Inspect all 8 results, especially the two known direct-ranking failures and score ties.
5. If 8/8 passes, prepare a clean 94-session scored-output evaluation.
6. Freeze PURE only after the clean final 94/94 evaluation passes.
7. Rerun Sequential, Recency, and ICL under the same final generation/runtime/output policy for the final thesis comparison table.

## Working rule
Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked. Do not overwrite the user's local uncommitted README changes.
