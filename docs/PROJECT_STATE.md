# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are all PASS / FROZEN. Local runtime memory profile is validated and stable. Phase 3 Review Extractor pilot v5 is PASS / ACCEPTED. Full extraction attempt 1 reached 131/134 successful; three blank-evidence failures are patched and ready for resume-only retry. Automatic Git handoff is active.**

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

### Pilot history
- v1: 3/3 technical PASS, but title-only attributes leaked into `key_features`; not accepted.
- v2: 3/3 technical PASS, but stronger prompt-only grounding still allowed title-derived attributes; not accepted.
- v3: mechanical verbatim grounding blocked title leakage but rejected a legitimate grounded paraphrase; representation rule too strict.
- v4: evidence-backed schema separated concise `value` from exact `evidence`; one title-derived unsupported evidence claim was caught and fail-fast stopped the pilot.

### Pilot v5 — PASS / ACCEPTED
Pilot v5 keeps the evidence-backed schema and validates every evidence entry independently. Unsupported entries are rejected/logged while other grounded entries from the same structurally valid response are preserved.

Pilot v5 result:
- successful extractions: 3/3
- failed extractions: 0
- accepted likes entries: 6
- accepted dislikes entries: 2
- accepted key-feature entries: 3
- rejected unsupported entries: 1
- accepted entries: 11
- total generated entries before grounding filter: 12
- pilot rejection rate: 8.33%
- total reported tokens: 1,898
- mean latency: 3.999 seconds/extraction
- status: PASS

The rejected entry was the Review-2 title-derived `backlit` evidence. It did not enter the profile-safe extraction. All stored profile-safe entries are review-grounded.

Known conservative limitation: audit-only `value` may occasionally be broader or less precisely aligned with the selected evidence span. The downstream profile does not use `value`; it uses only mechanically validated review evidence. Longer/overlapping evidence spans are allowed at this stage and will be consolidated by Profile Updater.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V5.md`.

### Full Review Extractor run — ATTEMPT 1 / INCOMPLETE
The accepted v5 configuration was run across all 134 required historical reviews.

Result:
- requested: 134
- successful: 131
- failed: 3
- users represented: 20
- accepted likes entries: 224
- accepted dislikes entries: 95
- accepted key-feature entries: 156
- rejected unsupported entries: 34
- total reported tokens: 90,055
- mean successful-request latency: 3.848 seconds
- total successful-request latency: 504.068 seconds (~8.40 minutes)
- status: INCOMPLETE

The 34 rejected unsupported entries were safely excluded and are not failures. The only three task failures all came from generated `key_features` entries with blank evidence strings (`evidence: ""`). The parser previously raised before the entry-level filter could classify those entries.

Retry patch:
- non-string evidence remains a structural error;
- blank evidence is now an individually rejected entry with reason `empty_evidence`;
- valid entries from the same response are preserved;
- schema/prompt additionally discourage blank evidence;
- no blank evidence can enter the profile-safe representation.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_FULL_RUN_ATTEMPT1.md`.

The accepted-v5 output directory is unchanged, `resume = true` remains enabled, and the next run should therefore skip 131 successful tasks and retry only the 3 failed tasks.

Review Extractor will be frozen only after 134/134 successful and final rejection statistics are recorded.

## Automatic experiment handoff
A reusable publisher writes compact local-run results to `handoff/latest.json`, commits only that path, and pushes the current branch. It never stages README or unrelated working-tree files and never auto-pulls/rebases/merges.

After ChatGPT reads a handoff, durable findings are moved into the appropriate docs and the mailbox is reset to `READY`. Git history is persistent, so secrets/private credentials must never be placed in the handoff. See `docs/EXPERIMENT_HANDOFF.md`.

Fatal wrapper-level exceptions can be run through `scripts/run_phase3_review_extractor_safe.py`, which publishes the full Python traceback into the handoff.

## Reproducibility note for final comparisons
The three currently frozen purchased-item baselines were collected before the stable runtime-throughput profile was finalized. Keep them as historical/frozen results. Before the final thesis comparison table, rerun compared methods under the same finalized runtime profile.

## Performance note
The first full Review Extractor attempt provides a useful throughput baseline: about 3.85 seconds per successful extraction, with ~8.40 minutes of successful-request latency across 131 completed tasks. Performance optimization will be benchmarked separately after the extractor is fully complete so runtime tuning is not mixed into the accepted scientific result.

## Current implementation status
Completed:
- Phase 1 preprocessing/session/candidate freeze
- local inference infrastructure and stable RAM profile
- Sequential, Recency-Focused, and ICL full baseline freezes
- JSON-Schema request support
- Review Extractor leakage-safe task builder, runner, parser, tests, and protocol docs
- pilots v1-v5 with documented failure modes and accepted grounding policy
- evidence-backed schema with entry-level conservative evidence filtering
- full Review Extractor attempt 1: 131/134 successful
- blank-evidence retry patch
- automatic Git experiment-handoff channel and safe traceback wrapper

## Next actions
1. Pull the current branch.
2. Run the unit-test suite.
3. Keep LM Studio on the finalized stable runtime profile.
4. Run `python scripts/run_phase3_review_extractor_safe.py` again.
5. Resume should skip the 131 successful tasks and retry only the 3 failures.
6. The runner automatically publishes the compact retry summary/error handoff; no terminal-output paste is needed.
7. When 134/134 are successful, freeze Review Extractor outputs and implement Profile Updater.
8. Then implement the PURE recommender and evaluate it on the frozen 94 sessions.
9. Separately benchmark safe throughput improvements after the extractor is frozen.
10. Rerun compared baselines under the finalized runtime profile before the final thesis comparison table.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
