# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are all PASS / FROZEN. Local runtime memory profile is validated and stable. Phase 3 Review Extractor pilots v1-v3 identified and isolated semantic-grounding failure modes; evidence-backed pilot v4 is now ready on the same 3 reviews. Automatic Git handoff is enabled so local experiment output no longer needs to be pasted manually.**

The active model is the local derivative model `llama-3.2-3b-instruct-uncensored`. Metrics from this model are labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` checkpoint.

## Environment
- Development: Python + VS Code
- Local-only inference through LM Studio / llama.cpp OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction: OpenAI-compatible HTTP client
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- Repository workflow: ChatGPT pushes code/docs; user pulls and runs locally; experiment runners can auto-publish compact results through `handoff/latest.json`
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
- Algorithm 1 applies Review Extractor to the incoming review at each time step;
- output contains likes, dislikes, and key features;
- Step 1 supplies ASIN/product/review context;
- the paper reports JSON-schema structured outputs.

Active reproduction choices:
- one canonical incoming interaction per LLM call, matching incremental `E(r_t)` behavior;
- prompt includes ASIN, canonical title, rating, and review text;
- rating inclusion is an explicit interpretation based on Figure 1;
- target/future reviews are never extracted early;
- the 94 frozen sessions require 134 unique historical review extractions;
- exact machine-readable schema and evidence validation are project-defined because the paper does not publish them.

### Pilot v1
3/3 technical PASS, but title-only attributes leaked into `key_features` for Reviews 1 and 2. Not accepted.

### Pilot v2
3/3 technical PASS, but stronger prompt-only grounding still allowed title-derived attributes. Not accepted.

### Pilot v3
Mechanical verbatim grounding successfully blocked title leakage, but the third review failed because `breathing LEDs` was a legitimate paraphrase of review text (`LEDs either breathe`) rather than an exact substring. Recorded as **grounding protection successful / representation rule too strict**. See `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V3.md`.

### Pilot v4 — ready
The schema now separates a concise model interpretation from exact review evidence:

```json
{"value": "breathing LEDs", "evidence": "LEDs either breathe"}
```

Every `evidence` field must be a contiguous review span. Only those verbatim evidence strings enter the downstream-safe extraction used by future profile construction; normalized `value` fields are kept only for audit. This prevents title-only content from entering the profile without rejecting grounded paraphrases.

Pilot v4 output is isolated at `outputs/phase3_review_extractor_v4/` and remains limited to the same first 3 reviews with `max_extractions = 3`, `resume = true`, `fail_fast = true`.

## Automatic experiment handoff
A reusable publisher now writes compact local-run results to `handoff/latest.json`, commits only that path with `git commit --only`, and pushes the current branch. It never stages README or unrelated working-tree files and never auto-pulls/rebases/merges.

The handoff is a mailbox, not a permanent result store. After ChatGPT reads a result, durable facts are moved into the appropriate result/protocol/project-state documents and the same handoff file is reset to `READY` in a later push.

Important: Git history is persistent, so secrets/private credentials must never be placed in the handoff. See `docs/EXPERIMENT_HANDOFF.md`.

## Reproducibility note for final comparisons
The three currently frozen purchased-item baselines were collected before the stable runtime-throughput profile above was finalized. Keep them as valid historical/frozen experiment records.

For thesis-grade final comparison with future PURE/review-aware methods, prefer a clean rerun of all compared methods under the same finalized runtime profile rather than overwriting the existing results.

## Current implementation status
Completed:
- Phase 1 preprocessing/session/candidate freeze
- local inference infrastructure and stable RAM profile
- Sequential, Recency-Focused, and ICL full baseline freezes
- JSON-Schema request support
- Review Extractor leakage-safe task builder, runner, parser, tests, and protocol docs
- pilots v1-v3 with documented failure modes
- evidence-backed v4 schema/validator
- automatic Git experiment-handoff channel

## Next actions
1. Pull the current branch.
2. Run the full unit-test suite.
3. Keep LM Studio on the finalized stable runtime profile.
4. Run `python scripts/run_phase3_review_extractor.py` for pilot v4.
5. The runner will automatically push `handoff/latest.json`; manual terminal-output copying is no longer required.
6. ChatGPT reads that handoff, records the durable result, and resets the mailbox.
7. If v4 passes, enable all 134 unique review extractions with resume.
8. Freeze Review Extractor outputs, then implement Profile Updater and PURE recommender.
9. Before the final thesis comparison table, rerun compared methods under the same finalized runtime profile.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
