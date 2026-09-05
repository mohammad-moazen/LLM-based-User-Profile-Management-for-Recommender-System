# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 Sequential pilot remains in prompt/output-interface validation.**

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

### Pilot attempt 1 — incomplete ranking
Session `A24ZRTTC3SPX8C:4` returned only 3 entries for 20 candidates. The original prompt contained pseudo-JSON with an ellipsis. This was classified as a prompt-formatting failure, not a recommender metric.

### Pilot attempt 2 — history identifiers leaked into output
After removing the ellipsis and explicitly requesting all 20 candidate ASINs, the same session returned **23 ASINs**:
- first 3 entries were the 3 purchase-history ASINs;
- remaining 20 entries were the candidate ASINs.

Parser correctly rejected the response with:
`Ranking length 23 does not match candidate count 20`.

No NDCG result is accepted from either failed attempt.

Diagnosis:
- showing ASINs in both history and candidate sections created output ambiguity for the small local model;
- ASINs are machine identifiers and provide no useful semantic recommendation signal;
- asking the model to reproduce machine identifiers is unnecessary for ranking quality.

### Active output-interface fix
The Sequential prompt now separates semantics from machine identifiers:
- purchase history: canonical product titles only;
- candidates: numbered product titles only (`Candidate 1` ... `Candidate N`);
- model output: a complete JSON permutation of candidate numbers 1..N;
- parser maps those ranked numbers back to the **unchanged frozen candidate ASIN order**;
- digit-only JSON strings are tolerated as serialization only;
- missing, duplicate, out-of-range, product-name, or ASIN outputs are rejected rather than repaired.

This changes only prompt/output serialization. It does **not** change users, histories, candidate sets, targets, or NDCG calculation.

## Current implementation
- `config/phase2.toml`
- `src/pure_recommender/baselines/sequential.py`
- `src/pure_recommender/phase2/config.py`
- `src/pure_recommender/phase2/io.py`
- `scripts/run_phase2_sequential.py`
- `tests/test_sequential_baseline.py`
- `docs/PHASE2_SEQUENTIAL_PROTOCOL.md`

Pilot settings remain:
- first 3 frozen sessions
- temperature: 0.0
- max output tokens: 512
- generation seed: 42
- fail-fast: true
- resume: true

## Next actions
1. Pull the numbered-candidate protocol update.
2. Run the full unit-test suite.
3. Re-run the same 3-session Sequential pilot.
4. Confirm all three model outputs are complete permutations of candidate numbers 1..20.
5. Inspect target ranks, latency, token usage, and raw responses.
6. If the pilot passes, set `max_sessions = 0` and run all 94 frozen sessions.
7. Record Sequential NDCG@1/@5/@10/@20.
8. Then implement Recency, ICL, Review Extractor, and full PURE.

## Working rule
This file is the authoritative current snapshot. Failed formatting runs are retained as debugging evidence but are never mixed into recommendation metrics. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
