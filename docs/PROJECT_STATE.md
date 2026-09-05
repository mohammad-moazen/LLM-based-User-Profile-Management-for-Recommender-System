# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 Sequential pilot implemented and ready for local execution.**

The user has explicitly chosen to continue with the currently available local derivative model `llama-3.2-3b-instruct-uncensored`. Phase 2 results produced with this model are valid project experiments but must be labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` backbone results.

## Agreed environment
- Development: Python + VS Code
- Repository workflow: ChatGPT pushes incremental code to GitHub; user pulls and runs locally
- Local-only LLM inference; no online inference APIs
- Runtime: Bionic / LM Studio local OpenAI-compatible server
- Confirmed endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction remains OpenAI-compatible so a later switch to vLLM, llama.cpp, or another local backend does not require rewriting PURE modules
- User hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- Models and datasets should remain outside drive C when possible

## Local LLM status
Confirmed:
- `GET /v1/models`: PASS
- Python chat completion through localhost: PASS
- full regression suite before Phase 2 implementation: 12/12 PASS
- localhost proxy interception bug fixed; local client explicitly bypasses environment/system HTTP proxies

Active model identifier:
- `llama-3.2-3b-instruct-uncensored`

Other observed local models include `qwen3-1.7b` and at least one embedding model.

Model policy is documented in `docs/MODEL_RUNTIME_POLICY.md`.

## Paper reference model vs active model
Paper reference backbone:
- `Llama-3.2-3B-Instruct`

Active project model by explicit user decision:
- `llama-3.2-3b-instruct-uncensored`

Therefore:
- current Phase 2 metrics are **not** exact paper-model reproduction;
- Phase 1 data/evaluation protocol remains unchanged and paper-oriented;
- an exact-reference model run can be added later as a separate experiment if desired.

## Agreed dataset
Amazon Review Data 2018, Video Games 5-core + Video Games metadata.

Local raw files:
- `Video_Games_5.json.gz`
- `meta_Video_Games.json.gz`

Raw datasets, processed datasets, model weights, caches, and large experiment outputs remain local and must not be committed.

## Canonical processed interaction schema
- `user_id`
- `asin`
- `title`
- `review_text`
- `rating`
- `timestamp`

A temporary `source_row_index` is retained only during preprocessing for deterministic equal-timestamp tie-breaking and is not exported as part of the public experiment schema.

## Core recommendation task
For each user, interactions are chronological. The recommender predicts the next purchased item from a 20-item candidate set containing:
- 1 ground-truth next item
- 19 deterministic randomly sampled non-interacted negatives

Initial `min_history = 3`, so the first prediction target is cleaned purchase 4.

Continuous evaluation generates every eligible next-item session for selected users. NDCG is averaged across sessions within each user first, then averaged across users.

## Frozen preprocessing policy v1
Canonical policy: `docs/PREPROCESSING_POLICY.md`.

Key rules:
1. Deduplicate metadata by ASIN using one usable non-empty title.
2. Drop review rows missing any required PURE field; do not synthesize review text from `summary`.
3. Drop interactions without a usable metadata title.
4. Collapse repeated `(user,item)` groups that are identical on PURE-relevant fields.
5. Exclude ambiguous repeated `(user,item)` groups when timestamp, rating, or review text conflicts.
6. Sort by timestamp with raw source-row order as deterministic tie-breaker.
7. Do not rerun iterative 5-core filtering after cleaning.
8. Negative candidates come from canonical items the user never interacts with anywhere in the cleaned full history.

These edge-case cleaning decisions are explicit reproduction choices because the paper does not document them.

## Frozen real-data Phase 1 result
- metadata rows: 84,819
- unique metadata ASINs: 71,911
- duplicate metadata ASIN groups: 12,908
- metadata empty titles: 11
- raw review rows: 497,577
- dropped missing-required rows: 158
- dropped rows without usable metadata title: 1,262 across 19 ASINs
- exact duplicate `(user,item)` groups collapsed: 22,782
- exact duplicate rows removed: 22,799
- ambiguous `(user,item)` groups excluded: 576
- ambiguous rows excluded: 1,348
- final canonical interactions: 472,010
- final users: 55,209
- final items: 17,388
- eligible users with `min_history=3`: 54,451
- history min/median/mean/max: 1 / 6.0 / 8.549511854951186 / 775
- deterministic pilot users: 20
- frozen continuous recommendation sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

Arithmetic audit:
`497,577 - 158 - 1,262 - 22,799 - 1,348 = 472,010`.

## PURE components to reproduce
1. Review Extractor
2. Profile Updater
3. LLM Recommender

Before full PURE, reproduce the purchased-item baselines in stages:
- Sequential
- Recency-focused
- ICL

## Phase 2 — Sequential baseline
Paper-derived behavior:
- provide only chronological purchased-item interactions and candidate list;
- rank candidates by likelihood of next purchase;
- use the frozen continuous sequential sessions;
- evaluate NDCG@1/@5/@10/@20 with per-user-first aggregation;
- use structured output for reliable post-processing.

The paper does not publish the exact Sequential prompt text or exact JSON schema. Our explicit protocol is documented in `docs/PHASE2_SEQUENTIAL_PROTOCOL.md`.

### Phase 2 implementation now present
- `config/phase2.toml`
- `src/pure_recommender/baselines/sequential.py`
- `src/pure_recommender/phase2/config.py`
- `src/pure_recommender/phase2/io.py`
- `scripts/run_phase2_sequential.py`
- `tests/test_sequential_baseline.py`

Key safeguards:
- reviews and ratings are never included in the Sequential prompt;
- target item is never marked for the LLM;
- history is oldest -> newest;
- candidates use title + ASIN;
- response must be a complete JSON permutation of candidate ASINs;
- malformed rankings are not silently repaired;
- runner supports resume/checkpoint behavior;
- per-session raw response, rank, NDCG, token usage, and latency are written locally.

### Initial Phase 2 pilot settings
- sessions: first 3 frozen sessions
- model: `llama-3.2-3b-instruct-uncensored`
- temperature: 0.0
- max output tokens: 512
- generation seed: 42
- fail-fast: true
- resume: true

If the 3-session pilot is clean, set `max_sessions = 0` and run all 94 frozen sessions.

## Current implementation status
Completed:
- dataset schema inspection and anomaly analysis
- preprocessing-policy v1 freeze
- canonical preprocessing and audit reporting
- deterministic continuous sessions and candidate sampling
- NDCG metric and paper-style aggregation
- Phase 1 synthetic and real-data validation
- Phase 1 formal freeze
- local OpenAI-compatible client and proxy-safe localhost transport
- local model endpoint and inference smoke test
- Phase 2 Sequential prompt/parser/config/runner implementation
- Phase 2 protocol documentation

Pending next:
1. Pull Phase 2 code
2. Run the full unit-test suite
3. Run the 3-session Sequential real-data pilot
4. Inspect raw ranking validity, target ranks, latency, and token usage
5. If pilot passes, run all 94 frozen sessions
6. Record Sequential NDCG@1/@5/@10/@20 in `EXPERIMENT_LOG.md`
7. Implement Recency and ICL baselines next
8. Then begin Review Extractor and PURE modules

## Working rule
This file is the authoritative snapshot of current project status. Update it whenever phase, backend, dataset, model, protocol, or next task changes. Important runs are appended to `docs/EXPERIMENT_LOG.md`; methodology decisions belong in dedicated policy/protocol documents.
