# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are PASS / FROZEN. Local runtime memory profile is validated and stable. Phase 3 Review Extractor is now PASS / FROZEN at 134/134 successful extractions. Next: benchmark safe throughput improvements, then implement Profile Updater. Automatic Git handoff is active.**

The active model is the local derivative model `llama-3.2-3b-instruct-uncensored`. Metrics from this model are labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` checkpoint.

## Environment
- Development: Python + VS Code
- Local-only inference through LM Studio / llama.cpp OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction: OpenAI-compatible HTTP client
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- repository workflow: ChatGPT pushes code/docs; user pulls and runs locally; experiment runners auto-publish compact results through `handoff/latest.json`
- do not overwrite the user's local uncommitted README changes

## Frozen Phase 1
Dataset: Amazon Review Data 2018 / Video Games 5-core + metadata.

Frozen real-data basis:
- raw reviews: 497,577
- final canonical interactions: 472,010
- final users: 55,209
- final items: 17,388
- eligible users with `min_history=3`: 54,451
- selected users: 20
- frozen continuous recommendation sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

The task is continuous next-item ranking: rank one ground-truth next item among 19 non-interacted negatives. NDCG is averaged across sessions within each user first, then averaged across users.

Frozen preprocessing decisions are documented in `docs/PREPROCESSING_POLICY.md`.

## Local LLM/runtime status
Confirmed:
- `GET /v1/models`: PASS
- Python chat completion through localhost: PASS
- localhost proxy interception bug fixed
- structured JSON Schema pass-through supported
- 100-request host-memory stability test: PASS

Validated stable LM Studio load profile:
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

Memory stability after warm-up and 100 requests:
- post-warm-up private RAM: 4.760 GB
- final private RAM: 4.761 GB
- displayed private-RAM delta: +0.000 GB
- displayed working-set delta: +0.000 GB
- mean request latency: 0.096 seconds

Detailed record: `docs/RUNTIME_MEMORY_STABILITY.md`.

## Phase 2 frozen purchased-item baselines
### Sequential — PASS / FROZEN
- successful sessions: 94
- NDCG@1: 0.061667
- NDCG@5: 0.182577
- NDCG@10: 0.227799
- NDCG@20: 0.366378
- total reported tokens: 60,669
- mean latency: 1.385 seconds/session

### Recency-Focused — PASS / FROZEN
- successful sessions: 94
- NDCG@1: 0.078333
- NDCG@5: 0.199726
- NDCG@10: 0.239947
- NDCG@20: 0.378652
- total reported tokens: 64,677
- mean latency: 1.394 seconds/session

### In-Context Learning (ICL) — PASS / FROZEN
- successful sessions: 94
- NDCG@1: 0.061667
- NDCG@5: 0.186356
- NDCG@10: 0.255724
- NDCG@20: 0.371370
- total reported tokens: 66,877
- mean latency: 1.343 seconds/session

Comparison record: `docs/PHASE2_BASELINE_COMPARISON.md`.

## Phase 3 PURE Review Extractor — PASS / FROZEN
Protocol: `docs/PHASE3_REVIEW_EXTRACTOR_PROTOCOL.md`.

Paper-derived behavior:
- Algorithm 1 applies Review Extractor to the incoming review at each time step;
- output contains likes, dislikes, and key features;
- Step 1 supplies ASIN/product/review context;
- the paper reports JSON-schema structured outputs.

Accepted reproduction choices:
- one canonical incoming interaction per LLM call, matching incremental `E(r_t)` behavior;
- prompt includes ASIN, canonical title, rating, and review text;
- rating inclusion is an explicit interpretation based on Figure 1;
- target/future reviews are never extracted early;
- evidence-backed JSON schema with audit-only normalized `value` plus review-grounded `evidence`;
- entry-level conservative evidence filtering;
- rejected or blank evidence never enters profile-safe data;
- exact schema/grounding validator are project-defined because the paper does not publish them.

Pilot history v1-v4 isolated title leakage and over-strict grounding. Pilot v5 was accepted and then used for the complete run.

Final frozen result:
- required unique extractions: 134
- successful extractions: 134
- failed extractions: 0
- users represented: 20
- accepted likes entries: 236
- accepted dislikes entries: 97
- accepted key-feature entries: 163
- total accepted entries: 496
- rejected unsupported/blank-evidence entries: 36
- total generated entries before grounding filter: 532
- final entry rejection rate: 6.77%
- prompt tokens: 70,502
- completion tokens: 22,327
- total reported tokens: 92,829
- total successful-request latency: 525.338 seconds (~8.76 minutes)
- mean latency: 3.920 seconds/extraction
- status: PASS / FROZEN

The 36 rejected entries are conservative-filter events, not task failures, and do not enter downstream profile-safe data. Profile Updater must consume only accepted `extraction` fields from the frozen local directory `outputs/phase3_review_extractor_v5/`.

Final record: `docs/PHASE3_REVIEW_EXTRACTOR_FINAL_RESULTS.md`.

## Automatic experiment handoff
A reusable publisher writes compact local-run results to `handoff/latest.json`, commits only that path, and pushes the current branch. It never stages README or unrelated working-tree files and never auto-pulls/rebases/merges.

After ChatGPT reads a handoff, durable findings are moved into the appropriate docs and the mailbox is reset to `READY`. Git history is persistent, so secrets/private credentials must never be placed in the handoff. See `docs/EXPERIMENT_HANDOFF.md`.

Fatal wrapper-level exceptions can be run through safe wrappers that publish the full Python traceback into the handoff.

## Reproducibility note for final comparisons
The three currently frozen purchased-item baselines were collected before the stable runtime-throughput profile was finalized. Keep them as historical/frozen results. Before the final thesis comparison table, rerun compared methods under the same finalized runtime profile.

## Performance note
The frozen Review Extractor provides a real throughput baseline: **3.920 seconds per extraction** and **~8.76 minutes total model-call latency for 134 successful extractions**. Performance tuning must be benchmarked separately and must not change model identity, context length, prompt semantics, output schema, K/V quantization, or accepted scientific outputs.

Preferred safe tuning order:
1. benchmark larger evaluation/physical batch sizes while keeping concurrency at 1;
2. only then benchmark concurrency 2 separately if memory remains stable;
3. do not alter context length, prompt content, model quantization, or K/V cache quantization merely for speed.

## Current implementation status
Completed:
- Phase 1 preprocessing/session/candidate freeze
- local inference infrastructure and stable RAM profile
- Sequential, Recency-Focused, and ICL full baseline freezes
- JSON-Schema request support
- Review Extractor leakage-safe task builder, runner, parser, tests, protocol docs
- pilots v1-v5 with documented failure modes and accepted grounding policy
- full Review Extractor run and resume-only retry
- Review Extractor 134/134 PASS / FROZEN
- automatic Git experiment-handoff channel and safe traceback wrapper

## Next actions
1. Benchmark safe runtime throughput improvements without changing the frozen scientific protocol.
2. Select/document a faster runtime profile only if memory remains stable and output behavior remains compatible.
3. Implement Profile Updater using only frozen accepted Review Extractor evidence.
4. Pilot Profile Updater chronologically with no future leakage.
5. Implement PURE recommender and evaluate on the frozen 94 sessions.
6. Rerun compared baselines under the finalized runtime profile before the final thesis comparison table.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
