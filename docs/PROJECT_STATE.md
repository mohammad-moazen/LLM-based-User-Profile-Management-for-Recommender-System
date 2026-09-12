# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are all PASS / FROZEN. Local runtime memory profile is validated and stable. Phase 3 Review Extractor pilots v1-v4 have isolated successive grounding failure modes. Pilot v5 is now ready with evidence-backed structured output plus entry-level conservative grounding filtering. Automatic Git handoff is active.**

The active model is the local derivative model `llama-3.2-3b-instruct-uncensored`. Metrics from this model are labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` checkpoint.

## Environment
- Development: Python + VS Code
- Local-only inference through LM Studio / llama.cpp OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction: OpenAI-compatible HTTP client
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- Repository workflow: ChatGPT pushes code/docs; user pulls and runs locally; experiment runners auto-publish compact results through `handoff/latest.json`
- Do not overwrite the user's local uncommitted README changes

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
3/3 technical PASS, but title-only attributes leaked into `key_features`. Not accepted.

### Pilot v2
3/3 technical PASS, but stronger prompt-only grounding still allowed title-derived attributes. Not accepted.

### Pilot v3
Mechanical verbatim grounding blocked title leakage but rejected a legitimate grounded paraphrase (`breathing LEDs` vs. review text `LEDs either breathe`). Grounding protection worked; representation rule was too strict.

### Pilot v4
Evidence-backed schema separated concise `value` from exact `evidence`. Review 1 passed. Review 2 contained three useful grounded entries plus one unsupported title-derived key feature:

```json
{"value": "backlit", "evidence": "rainbow backlit wired gaming keyboard mouse combo"}
```

That evidence is absent from the review and came from product metadata. The deterministic validator correctly rejected the response; `fail_fast = true` then stopped before Review 3. Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V4.md`.

### Pilot v5 — ready
Pilot v5 keeps the evidence-backed schema but validates entries independently. Structurally valid grounded entries are retained; unsupported evidence entries are rejected and explicitly logged rather than causing all valid entries from that response to be discarded.

Important invariants:
- rejected entries are never rewritten or replaced;
- only validated review evidence can enter the downstream profile-safe extraction;
- rejected field/value/evidence/reason are retained for audit;
- schema violations still fail the response;
- Profile Updater remains responsible for redundancy/conflict consolidation.

Pilot v5 output is isolated at `outputs/phase3_review_extractor_v5/` and remains limited to the same first 3 reviews with `max_extractions = 3`, `resume = true`, `fail_fast = true`.

## Automatic experiment handoff
A reusable publisher writes compact local-run results to `handoff/latest.json`, commits only that path, and pushes the current branch. It never stages README or unrelated working-tree files and never auto-pulls/rebases/merges.

After ChatGPT reads a handoff, durable findings are moved into the appropriate docs and the mailbox is reset to `READY`. Git history is persistent, so secrets/private credentials must never be placed in the handoff. See `docs/EXPERIMENT_HANDOFF.md`.

## Reproducibility note for final comparisons
The three currently frozen purchased-item baselines were collected before the stable runtime-throughput profile was finalized. Keep them as historical/frozen results. Before the final thesis comparison table, rerun compared methods under the same finalized runtime profile.

## Current implementation status
Completed:
- Phase 1 preprocessing/session/candidate freeze
- local inference infrastructure and stable RAM profile
- Sequential, Recency-Focused, and ICL full baseline freezes
- JSON-Schema request support
- Review Extractor leakage-safe task builder, runner, parser, tests, and protocol docs
- pilots v1-v4 with documented failure modes
- evidence-backed schema
- entry-level conservative evidence filter for pilot v5
- automatic Git experiment-handoff channel

## Next actions
1. Pull the current branch.
2. Run the full unit-test suite.
3. Keep LM Studio on the finalized stable runtime profile.
4. Run `python scripts/run_phase3_review_extractor.py` for pilot v5.
5. The runner automatically pushes `handoff/latest.json`; no terminal-output paste is needed.
6. ChatGPT reads the handoff, records the durable result, and resets the mailbox.
7. If v5 is clean, enable all 134 unique review extractions with resume and `fail_fast = false`.
8. Freeze Review Extractor outputs, then implement Profile Updater and PURE recommender.
9. Rerun compared baselines under the finalized runtime profile before the final thesis comparison table.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
