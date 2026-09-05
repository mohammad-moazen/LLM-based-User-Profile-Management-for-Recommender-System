# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 Sequential 3-session real-data pilot PASS; full 94-session Sequential run is now enabled.**

The user has explicitly chosen to continue with the local derivative model `llama-3.2-3b-instruct-uncensored`. Current Phase 2 metrics must therefore be labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` backbone results.

## Environment
- Development: Python + VS Code
- Local-only inference through Bionic / LM Studio OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction: OpenAI-compatible HTTP client
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM

## Frozen Phase 1
Dataset: Amazon Review Data 2018 / Video Games 5-core + metadata.

Frozen real-data result:
- raw reviews: 497,577
- final canonical interactions: 472,010
- final users: 55,209
- final items: 17,388
- eligible users with `min_history=3`: 54,451
- pilot users: 20
- frozen sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

The task remains: use chronological history to rank one ground-truth next item among 19 non-interacted negatives. NDCG is averaged within user first, then across users.

## Phase 2 — Sequential baseline
Paper-derived behavior preserved:
- model sees chronological purchased-item history and the candidate list only;
- reviews, ratings, profiles, future interactions, and target markers are excluded;
- the frozen Phase 1 candidate sets are reused unchanged;
- NDCG@1/@5/@10/@20 is evaluated with the paper-style user-first aggregation.

The paper does not publish the exact Sequential prompt or output schema. Our explicit protocol is documented in `docs/PHASE2_SEQUENTIAL_PROTOCOL.md`.

### Output-interface debugging history
Two early pilot attempts were rejected and are not included in metrics:

1. A pseudo-JSON prompt containing an ellipsis led the model to output only 3 entries for 20 candidates.
2. After requesting all 20 ASINs explicitly, the model returned 23 ASINs: the 3 history ASINs plus the 20 candidate ASINs.

These failures were classified as prompt/output-formatting defects, not recommendation-performance results.

### Active numbered-candidate protocol
The stable interface now uses:
- purchase history: canonical product titles only;
- candidates: numbered product titles only (`Candidate 1` ... `Candidate N`);
- model output: a complete JSON permutation of candidate numbers 1..N;
- runner mapping: ranked candidate numbers -> unchanged frozen candidate ASIN order;
- parser rejection for missing, duplicate, out-of-range, product-name, or ASIN outputs.

This changes only serialization. Users, histories, candidate sets, targets, and metrics remain unchanged.

### Validated real-data pilot
The first 3 frozen sessions completed successfully under the numbered-candidate protocol:
- successful sessions: 3
- failed sessions: 0
- users represented: 2
- NDCG@1: 0.000000
- NDCG@5: 0.000000
- NDCG@10: 0.000000
- NDCG@20: 0.245522
- total reported tokens: 1,898
- mean latency: 1.406 seconds/session
- status: PASS

These NDCG values are retained as a pilot diagnostic only; three sessions are too small to interpret as the Sequential baseline's substantive performance.

## Full 94-session run configuration
Checked-in `config/phase2.toml` now uses:
- `max_sessions = 0` -> all 94 frozen sessions
- `resume = true` -> the 3 successful pilot sessions are skipped automatically
- `fail_fast = false` -> one malformed response does not discard progress on the remaining sessions
- temperature: 0.0
- max output tokens: 512
- generation seed: 42

Invalid model outputs remain excluded from NDCG. If any occur, the summary is `INCOMPLETE`; rerunning retries failed sessions because resume skips only `status="ok"` records.

## Current implementation
- `config/phase2.toml`
- `src/pure_recommender/baselines/sequential.py`
- `src/pure_recommender/phase2/config.py`
- `src/pure_recommender/phase2/io.py`
- `scripts/run_phase2_sequential.py`
- `tests/test_sequential_baseline.py`
- `docs/PHASE2_SEQUENTIAL_PROTOCOL.md`

## Next actions
1. Pull the full-run configuration.
2. Keep the local model server active.
3. Run `python scripts/run_phase2_sequential.py` to process all frozen sessions.
4. If the run is `INCOMPLETE`, rerun the same command until all failed sessions have valid outputs or investigate persistent failures.
5. Once all 94 sessions are successful, record final Sequential NDCG@1/@5/@10/@20, token usage, and latency.
6. Then implement Recency and ICL baselines.
7. After baselines are stable, begin Review Extractor and full PURE modules.

## Working rule
This file is the authoritative current snapshot. Failed formatting runs are retained as debugging evidence but are never mixed into recommendation metrics. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
