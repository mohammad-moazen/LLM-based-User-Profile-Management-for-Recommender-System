# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are all PASS / FROZEN.**

The active model is the local derivative model `llama-3.2-3b-instruct-uncensored`. Metrics from this model are labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` checkpoint.

## Environment
- Development: Python + VS Code
- Local-only inference through Bionic / LM Studio OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction: OpenAI-compatible HTTP client
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- Repository workflow: ChatGPT pushes incremental code/docs; user pulls, runs locally, and sends terminal results
- Do not overwrite the user's local uncommitted README changes

## Frozen Phase 1
Dataset: Amazon Review Data 2018 / Video Games 5-core + metadata.

Frozen real-data basis:
- raw reviews: 497,577
- final canonical interactions: 472,010
- final users: 55,209
- final items: 17,388
- eligible users with `min_history=3`: 54,451
- selected pilot users: 20
- frozen continuous recommendation sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

The task is continuous next-item ranking: rank one ground-truth next item among 19 non-interacted negatives. NDCG is averaged across sessions within each user first, then averaged across users.

Frozen preprocessing decisions are documented in `docs/PREPROCESSING_POLICY.md`. Edge-case cleaning and deterministic sampling rules not specified by the paper are explicit reproduction choices.

## Local LLM/runtime status
Confirmed:
- `GET /v1/models`: PASS
- Python chat completion through localhost: PASS
- localhost proxy interception bug fixed
- numbered-candidate JSON ranking interface validated across all three full Phase 2 baseline runs

Active model:
- `llama-3.2-3b-instruct-uncensored`

Model/runtime policy: `docs/MODEL_RUNTIME_POLICY.md`.

### Runtime memory observation
The user observed cumulative-looking system-RAM growth in `llama-server.exe` across repeated runs. During the first full ICL run, one session failed and the run reached 93/94. The local server was restarted to clear process-local RAM/cache state without changing model or generation settings. Resume mode then retried only the failed session and the final ICL run reached 94/94 PASS.

A fixed server cache/runtime policy should be documented before final thesis-grade efficiency comparisons. If that policy materially changes from the current runs, all compared baselines should be rerun under the same policy.

## Shared Phase 2 output interface
After early Sequential formatting failures, the stable interface is:
- purchase semantics represented with canonical product titles;
- ASINs hidden from the LLM prompt;
- candidates rendered as numbered titles (`Candidate 1` ... `Candidate 20`);
- model output required to be a JSON permutation of candidate numbers 1..20;
- runner maps ranked numbers back to the unchanged frozen ASIN order;
- malformed, missing, duplicate, out-of-range, product-name, or ASIN outputs are rejected rather than repaired.

The rejected formatting-debug runs are not included in frozen metrics.

## Phase 2 frozen purchased-item baselines

### Sequential — PASS / FROZEN
Protocol: `docs/PHASE2_SEQUENTIAL_PROTOCOL.md`

Result: `docs/PHASE2_SEQUENTIAL_RESULTS.md`

- successful sessions: 94
- failed sessions: 0
- users: 20
- NDCG@1: 0.061667
- NDCG@5: 0.182577
- NDCG@10: 0.227799
- NDCG@20: 0.366378
- total reported tokens: 60,669
- mean latency: 1.385 seconds/session

### Recency-Focused — PASS / FROZEN
Protocol: `docs/PHASE2_RECENCY_PROTOCOL.md`

Result: `docs/PHASE2_RECENCY_RESULTS.md`

- successful sessions: 94
- failed sessions: 0
- users: 20
- NDCG@1: 0.078333
- NDCG@5: 0.199726
- NDCG@10: 0.239947
- NDCG@20: 0.378652
- total reported tokens: 64,677
- mean latency: 1.394 seconds/session

### In-Context Learning (ICL) — PASS / FROZEN
Protocol: `docs/PHASE2_ICL_PROTOCOL.md`

Result: `docs/PHASE2_ICL_RESULTS.md`

- successful sessions: 94
- failed sessions: 0
- users: 20
- NDCG@1: 0.061667
- NDCG@5: 0.186356
- NDCG@10: 0.255724
- NDCG@20: 0.371370
- total reported tokens: 66,877
- mean latency: 1.343 seconds/session

The first full ICL attempt (93/94) is retained only as runtime/debugging history and is not the final ICL result.

## Cross-baseline comparison
Comparison record: `docs/PHASE2_BASELINE_COMPARISON.md`

Current local ranking by cutoff:
- NDCG@1: Recency-Focused best
- NDCG@5: Recency-Focused best
- NDCG@10: ICL best
- NDCG@20: Recency-Focused best

These comparisons are descriptive for the frozen local derivative-model experiment only.

## Current implementation status
Completed:
- dataset schema/anomaly analysis and preprocessing-policy freeze
- canonical preprocessing and deterministic continuous session generation
- candidate leakage validation and paper-style NDCG aggregation
- Phase 1 real-data freeze
- local OpenAI-compatible client and inference smoke test
- robust numbered-candidate output serialization
- Sequential full 94-session run and freeze
- Recency-Focused full 94-session run and freeze
- ICL full 94-session run and freeze
- frozen comparison of all three purchased-item baselines
- runtime RAM/cache observation documented

## Next phase
Before running substantially longer review-aware prompts, lock down and record a stable local-server cache/runtime policy so RAM behavior is controlled and comparable.

Then implement the review-aware/PURE path in paper order:
1. Review Extractor (likes, dislikes, key features)
2. Profile Updater (remove redundancy/overlap/conflicts while preserving crucial information)
3. PURE recommender using the evolving profile and purchased-item context
4. Review-aware baseline variants where required for comparison
5. Pilot on a few frozen sessions, then full 94-session evaluation

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
