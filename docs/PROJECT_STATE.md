# Project State

## Project
Step-by-step Python reproduction of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS.** The canonical data/evaluation pipeline is stable, the localhost OpenAI-compatible client passes its full regression suite, and end-to-end local model inference has been validated. The next gate before paper-aligned Phase 2 metrics is loading the intended `Llama-3.2-3B-Instruct` reference model and recording its exact runtime settings.

## Agreed environment
- Development: Python + VS Code
- Repository workflow: ChatGPT pushes incremental code to GitHub; user pulls and runs locally
- Local-only LLM inference; no online inference APIs
- Preferred local serving path: Bionic / LM Studio local model API using an OpenAI-compatible localhost endpoint
- Confirmed local endpoint: `http://127.0.0.1:1234/v1`
- Architecture must keep the LLM backend abstract so it can later switch to vLLM, llama.cpp, or another local OpenAI-compatible backend
- Reference reproduction model: `Llama-3.2-3B-Instruct`
- Initial quantization target: GGUF `Q8_0`; fall back to `Q6_K`, `Q5_K_M`, or `Q4_K_M` if memory/performance requires it
- Initial context length target: 8192 tokens
- User hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- Models and datasets must be stored outside drive C when possible

## Local model endpoint status
`GET /v1/models`: PASS.

End-to-end Python chat completion through the local OpenAI-compatible server: PASS.

Full unit-test suite after fixing localhost proxy interception: 12/12 PASS.

The local HTTP client explicitly bypasses environment/system HTTP proxies so requests to localhost remain direct.

Observed exposed model identifiers include:
- `llama-3.2-3b-instruct-uncensored`
- `qwen3-1.7b`
- at least one embedding model

Important: `llama-3.2-3b-instruct-uncensored` is treated only as a derivative model suitable for connectivity testing. It is **not** silently equated with the paper's `Llama-3.2-3B-Instruct` reference model. This distinction is documented in `docs/MODEL_RUNTIME_POLICY.md`.

## Agreed dataset
Amazon Review Data 2018, Video Games 5-core + Video Games metadata.

Local files currently used:
- `Video_Games_5.json.gz`
- `meta_Video_Games.json.gz`

The repository must never track raw datasets, model weights, generated caches, or large experiment artifacts.

## Confirmed review schema fields used by PURE
- `reviewerID` -> `user_id`
- `asin`
- `reviewText` -> `review_text`
- `overall` -> `rating`
- `unixReviewTime` -> `timestamp`

## Confirmed metadata schema fields used initially
- `asin`
- `title`

## Canonical processed interaction schema
- `user_id`
- `asin`
- `title`
- `review_text`
- `rating`
- `timestamp`

A temporary `source_row_index` is allowed during preprocessing for deterministic tie-breaking when timestamps are equal; it is not part of the final experiment schema.

## Core task definition
For each user, interactions are sorted chronologically. The recommender predicts the next purchased item from a candidate set containing one ground-truth item and 19 randomly sampled non-interacted items. The initial implementation uses `min_history = 3`, so the first prediction target is purchase 4.

## PURE components to reproduce
1. Review Extractor
2. Profile Updater
3. LLM Recommender

## Frozen preprocessing policy v1
Canonical policy is documented in `docs/PREPROCESSING_POLICY.md`.

Key rules:
1. Deduplicate metadata by ASIN, selecting one usable non-empty title.
2. Drop review rows missing any required PURE field; do not synthesize review text from `summary`.
3. Drop interactions whose ASIN has no usable product title.
4. Collapse repeated `(user, item)` groups that are identical on PURE-relevant fields.
5. Exclude ambiguous repeated `(user, item)` groups when timestamp, rating, or review text conflicts.
6. Sort chronologically by timestamp and use raw source-row order only as a deterministic tie-breaker for equal timestamps.
7. Do not rerun iterative 5-core filtering after cleaning; determine eligibility from cleaned histories with configurable `min_history`.
8. Candidate items come from products present in the cleaned canonical interaction dataset; each session uses one target plus 19 negatives sampled without replacement from items the user never interacts with anywhere in the cleaned full history. Sampling and candidate ordering are deterministic under recorded seeds.

Important provenance rule: these edge-case cleaning decisions are part of this reproduction. The paper does not document them, so they must never be attributed to the paper authors.

## Phase 1 implementation
- `config/phase1.toml`: checked-in deterministic experiment settings
- `src/pure_recommender/config.py`: typed config loader
- `src/pure_recommender/data/preprocessing.py`: frozen preprocessing-policy v1
- `src/pure_recommender/data/sessions.py`: chronological histories, deterministic user selection, 20-item candidate construction, leakage validation
- `src/pure_recommender/evaluation/metrics.py`: NDCG@k for the one-ground-truth setup plus paper-style user-level aggregation
- `scripts/run_phase1.py`: full local Phase 1 runner and audit report writer
- `tests/`: synthetic unit tests for eligibility, first target timestep, deterministic candidate construction, leakage prevention, and NDCG behavior
- local generated outputs go under `outputs/phase1/` and remain ignored by Git

## Local LLM integration implementation
- `config/local_llm.toml`: local endpoint/model/generation settings for smoke testing
- `src/pure_recommender/llm/config.py`: typed local-LLM config loader
- `src/pure_recommender/llm/client.py`: standard-library OpenAI-compatible client for `/v1/models` and `/v1/chat/completions`
- `scripts/smoke_test_local_llm.py`: end-to-end Python -> localhost -> model inference test
- `tests/test_llm_client.py`: mock HTTP tests for model listing, chat completion, and localhost proxy bypass
- `docs/MODEL_RUNTIME_POLICY.md`: explicit distinction between runtime smoke-test models and the paper-reference model

The LLM code is intentionally independent from LM Studio-specific SDK calls so the backend can later be changed by configuration.

## Frozen real-data Phase 1 result
From the successful local run:
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
- cleaned history length: min=1, median=6.0, mean=8.549511854951186, max=775
- deterministic selected users: 20
- generated continuous recommendation sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS
- synthetic/unit validation before the real run: 9/9 tests PASS

Arithmetic audit:
`497,577 - 158 - 1,262 - 22,799 - 1,348 = 472,010`, exactly matching the final interaction count.

Representative real session also confirmed:
- observed history length = 3
- target = fourth cleaned interaction
- 20 candidates
- target appears exactly once
- target position is deterministically shuffled

## Phase 1 freeze criteria
All satisfied:
- deterministic preprocessing according to documented policy v1
- chronological user histories
- first prediction after 3 observed interactions
- deterministic 1-positive + 19-negative candidate sets
- full-history exclusion from negative pool
- candidate leakage/invariant checks pass
- NDCG@1/@5/@10/@20 infrastructure implemented
- paper-style per-user then across-user aggregation implemented
- synthetic unit tests pass
- successful real-data run and audit counts captured

## Current implementation status
Completed:
- Repository initialization and branch setup
- Dataset schema inspection and validation
- Dataset anomaly analysis
- Frozen preprocessing policy v1
- Documentation framework
- Canonical preprocessing implementation
- Chronological history construction
- Deterministic small-user selection
- Deterministic candidate generation with 1 target + 19 negatives
- Candidate leakage checks
- NDCG metric implementation and paper-style aggregation
- Synthetic unit tests; 9/9 passed before LLM integration
- Real local Phase 1 end-to-end run: PASS
- Phase 1 formal freeze: PASS
- Local OpenAI-compatible `/v1/models` endpoint discovery: PASS
- Backend-agnostic local LLM client: PASS
- Full current unit-test suite: 12/12 PASS
- End-to-end local LLM smoke test: PASS

Pending next:
1. Load the intended `Llama-3.2-3B-Instruct` reference model locally
2. Confirm its exact identifier through `/v1/models`
3. Record exact quantization, context length, GPU offload, runtime/backend version, and generation settings
4. Re-run the smoke test using that exact reference model
5. Implement Phase 2 Sequential baseline against the frozen 94-session pilot
6. Evaluate NDCG@1/@5/@10/@20 using paper-style per-user aggregation
7. Only then scale beyond the 20-user pilot

## Working rule
This file is the authoritative snapshot of current project status. Update it whenever the phase, backend, dataset, model, cleaning policy, or next task changes. Important experiment runs are appended to `EXPERIMENT_LOG.md`; methodology decisions belong in dedicated docs such as `PREPROCESSING_POLICY.md` and `MODEL_RUNTIME_POLICY.md`.
