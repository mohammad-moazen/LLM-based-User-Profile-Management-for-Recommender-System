# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are all PASS / FROZEN. Local runtime memory profile is validated and stable. Phase 3 Review Extractor pilots v1/v2 exposed semantic grounding weaknesses; pilot v3 now adds mechanical verbatim-review validation and is ready on the same 3 reviews.**

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

Paper-derived behavior:
- Algorithm 1 applies the Review Extractor to the incoming review at each time step;
- output representation contains likes, dislikes, and key features;
- Step 1 supplies ASIN/product/review context;
- the paper reports JSON-schema structured outputs.

Active reproduction choices:
- one canonical incoming interaction per LLM call, matching incremental `E(r_t)` behavior;
- prompt includes ASIN, canonical title, rating, and review text;
- rating inclusion is an explicit interpretation based on Figure 1;
- exact JSON schema is project-defined because the paper does not publish it;
- target/future reviews are never extracted early;
- the 94 frozen sessions require 134 unique historical review extractions.

### Pilot v1 — technical PASS / semantic refinement required
3/3 calls succeeded with schema-valid outputs, but qualitative inspection found title-only features copied into `key_features` for Reviews 1 and 2. This pilot is retained only for auditability.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`.

### Pilot v2 — technical PASS / semantic grounding still insufficient
The stronger prompt improved grounding but did not fully solve it. In Review 2, `backlit keyboard` and `wired mouse` were still title-derived and unsupported by the review text. Review 1 also showed key-feature entries that mostly duplicated/rephrased the driver-update complaint. Review 3 was largely grounded.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V2.md`.

### Pilot v3 — ready
Prompt-only grounding is replaced by prompt + mechanical validation:
- every extracted string must be a short contiguous verbatim span from the review text;
- the parser validates generated entries against the canonical review after case/whitespace normalization;
- title-only, inferred, or paraphrased entries are rejected rather than silently filtered;
- metadata remains visible for paper alignment but cannot become accepted profile evidence unless the same text occurs in the review;
- output directory is isolated at `outputs/phase3_review_extractor_v3/`.

Pilot v3 remains limited to the same first 3 reviews with `max_extractions = 3`, `resume = true`, and `fail_fast = true`.

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
- Phase 3 Review Extractor pilots v1 and v2 with qualitative inspection
- mechanical verbatim-review grounding validator for pilot v3

## Next actions
1. Pull the current branch.
2. Run the full unit-test suite.
3. Keep LM Studio loaded with the finalized stable runtime profile.
4. Run `python scripts/run_phase3_review_extractor.py` for pilot v3 on the same first 3 reviews.
5. Run `python scripts/inspect_phase3_review_extractor_pilot.py` and inspect the accepted verbatim spans.
6. If pilot v3 is clean, enable all 134 unique review extractions with resume.
7. Freeze the accepted Review Extractor outputs needed by the 94 sessions.
8. Implement Profile Updater and then the PURE recommender.
9. Before the final thesis comparison table, rerun all compared methods under the same finalized runtime profile.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
