# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are all PASS / FROZEN. Local runtime memory profile is validated and stable. Phase 3 Review Extractor pilot v1 passed technically but exposed title-only feature extraction; prompt-grounding refinement is implemented and pilot v2 is ready on the same 3 reviews.**

The active model is the local derivative model `llama-3.2-3b-instruct-uncensored`. Metrics from this model are labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` checkpoint.

## Environment
- Development: Python + VS Code
- Local-only inference through LM Studio / llama.cpp OpenAI-compatible server
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
- 100-request host-memory stability test: PASS
- generic OpenAI-compatible `response_format` pass-through added for structured JSON Schema output

Active model:
- `llama-3.2-3b-instruct-uncensored`

Model/runtime policy: `docs/MODEL_RUNTIME_POLICY.md`.

### Validated stable LM Studio load profile
- Context Length: 8192
- GPU Offload: 28 / max
- CPU Thread Pool: 7
- Evaluation Batch Size: 512
- Physical Batch Size: 256
- Max Concurrent Predictions: 1
- Unified KV Cache: ON
- Context Checkpoints: 32
- KV Cache Offload to GPU: ON
- Keep Model in Memory: ON
- mmap: ON
- Speculative Decoding: OFF
- Flash Attention: ON
- K/V Cache Quantization: OFF

Memory stability result after warm-up and 100 repeated requests:
- post-warm-up private RAM: 4.760 GB
- final private RAM: 4.761 GB
- displayed private-RAM delta: +0.000 GB
- displayed working-set delta: +0.000 GB
- mean request latency: 0.096 seconds

Interpretation: stable plateau; no sustained cumulative host-RAM growth observed in the controlled test. No further RAM-saving restriction is currently justified.

Detailed record: `docs/RUNTIME_MEMORY_STABILITY.md`.

## Phase 2 frozen purchased-item baselines

### Sequential — PASS / FROZEN
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
- successful sessions: 94
- failed sessions: 0
- users: 20
- NDCG@1: 0.061667
- NDCG@5: 0.186356
- NDCG@10: 0.255724
- NDCG@20: 0.371370
- total reported tokens: 66,877
- mean latency: 1.343 seconds/session

Comparison record: `docs/PHASE2_BASELINE_COMPARISON.md`.

## Phase 3 PURE Review Extractor
Protocol: `docs/PHASE3_REVIEW_EXTRACTOR_PROTOCOL.md`.

Paper-derived component behavior:
- Algorithm 1 applies the Review Extractor to the incoming review at each time step;
- extracted representation has three categories: likes, dislikes, key features;
- Step 1 supplies product/review context and asks the LLM to analyze those three categories;
- the paper reports JSON-schema structured outputs for reliable automatic processing.

Active reproduction choices are explicit:
- one canonical incoming interaction is extracted per LLM call, matching the incremental `E(r_t)` algorithm;
- prompt includes ASIN, canonical title, rating, and review text;
- rating is included because Figure 1 states that PURE uses ratings, although the published Step-1 text does not list rating as a separate placeholder;
- exact JSON schema is project-defined because the paper does not publish it;
- schema keys are `likes`, `dislikes`, and `key_features`, each an array of strings;
- extractor output is not deduplicated or semantically repaired; redundancy/conflict handling is reserved for Profile Updater;
- extraction tasks are derived from frozen sessions so a target review is never available before its purchase occurs;
- the 94 frozen sessions require 134 unique historical review extractions.

### Pilot v1 — technical PASS / semantic refinement required
The first 3 real review extractions completed successfully:
- successful extractions: 3
- failed extractions: 0
- users represented: 1
- likes entries: 8
- dislikes entries: 2
- key-feature entries: 10
- total reported tokens: 1,063
- mean latency: 2.109 seconds
- schema/transport status: PASS

Qualitative inspection found a semantic issue: for Review 1, `Cherry MX Red switches` and `RGB LED lighting` were copied from the product title although the review text did not discuss them; for Review 2, `backlit keyboard`, `wired connection`, `gaming mouse`, and `white color` were similarly title-derived rather than review-grounded. Review 3 was largely grounded.

This is not out-of-input hallucination because the product title was visible, but it is too weakly grounded for an evolving user-preference profile. Pilot v1 is retained for auditability and is not the accepted extraction set.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`.

### Pilot v2 — ready
The extractor prompt now explicitly requires every preference/key-feature entry to be grounded in the review text itself:
- ASIN/title are identity context only;
- rating is overall sentiment context only;
- a title-only attribute must not be extracted unless the review also mentions or clearly describes it;
- empty arrays are preferred over unsupported entries.

The same 3 reviews will be rerun with unchanged model/generation/runtime settings into a fresh directory:

`outputs/phase3_review_extractor_v2/`

This prevents resume from reusing v1 results and preserves the original pilot artifacts.

## Reproducibility note for final comparisons
The three currently frozen purchased-item baselines were collected before the stable runtime-throughput profile above was finalized. Keep them as valid historical/frozen experiment records.

For thesis-grade final comparison with future PURE/review-aware methods, prefer a clean rerun of all compared methods under the same finalized runtime profile rather than overwriting the existing results.

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
- local runtime memory-stability validation and finalized load profile
- structured JSON-Schema request support in the local LLM client
- PURE Review Extractor prompt/schema/parser, leakage-safe task builder, config, runner, tests, and protocol documentation
- Phase 3 Review Extractor pilot v1 technical run and qualitative inspection
- review-grounding prompt refinement and isolated pilot-v2 output configuration

## Next actions
1. Pull the current branch.
2. Run the full unit-test suite.
3. Keep LM Studio loaded with the finalized stable runtime profile.
4. Run `python scripts/run_phase3_review_extractor.py` for pilot v2 on the same first 3 reviews.
5. Run `python scripts/inspect_phase3_review_extractor_pilot.py` and verify that title-only features have disappeared unless supported by the review.
6. If pilot v2 is clean, enable all 134 unique review extractions with resume.
7. Freeze the accepted Review Extractor outputs needed by the 94 sessions.
8. Implement Profile Updater and then the PURE recommender.
9. Before the final thesis comparison table, rerun all compared methods under the same finalized runtime profile.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
