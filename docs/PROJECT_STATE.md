# Project State

## Project
Step-by-step Python reproduction of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
Phase 1 has completed its first successful full local run through real-data recommendation-session generation. Exact post-cleaning/report counts from the `PURE PHASE 1 REPORT` still need to be captured before Phase 1 is formally frozen. Local inference setup remains pending in parallel.

## Agreed environment
- Development: Python + VS Code
- Repository workflow: ChatGPT pushes incremental code to GitHub; user pulls and runs locally
- Local-only LLM inference; no online inference APIs
- Preferred local serving path: Bionic / LM Studio local model API using an OpenAI-compatible localhost endpoint
- Architecture must keep the LLM backend abstract so it can later switch to vLLM, llama.cpp, or another local OpenAI-compatible backend
- Reference reproduction model: `Llama-3.2-3B-Instruct`
- Initial quantization target: GGUF `Q8_0`; fall back to `Q6_K`, `Q5_K_M`, or `Q4_K_M` if memory/performance requires it
- Initial context length target: 8192 tokens
- User hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- Models and datasets must be stored outside drive C when possible

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

## Phase 1 implementation now present
- `config/phase1.toml`: checked-in deterministic experiment settings
- `src/pure_recommender/config.py`: typed config loader
- `src/pure_recommender/data/preprocessing.py`: frozen preprocessing-policy v1
- `src/pure_recommender/data/sessions.py`: chronological histories, deterministic user selection, 20-item candidate construction, leakage validation
- `src/pure_recommender/evaluation/metrics.py`: NDCG@k for the one-ground-truth setup plus paper-style user-level aggregation
- `scripts/run_phase1.py`: full local Phase 1 runner and audit report writer
- `tests/`: synthetic unit tests for eligibility, first target timestep, deterministic candidate construction, leakage prevention, and NDCG behavior
- local generated outputs go under `outputs/phase1/` and remain ignored by Git

## Real-data Phase 1 validation status
Confirmed from the first real local run:
- `run_phase1.py` completed successfully
- first session id: `A24ZRTTC3SPX8C:4`
- observed history contains exactly 3 interactions
- target is the 4th cleaned interaction
- candidate set contains exactly 20 items
- ground-truth target appears exactly once and was shuffled to candidate position 17 in the displayed sample
- sample history (gaming keyboards) and target (gaming mouse) are semantically plausible
- random negative candidates span unrelated Video Games items, which is expected under the paper-aligned random non-interacted sampling setup

Still required before Phase 1 freeze:
- capture exact post-cleaning interaction/user/item counts from `PURE PHASE 1 REPORT`
- capture exact eligible-user and generated-session counts
- confirm no report-level validation failures or anomalies

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
- Synthetic unit tests; 9 tests passed before push
- First real local Phase 1 end-to-end session-generation run: PASS

Pending next:
1. Record exact `PURE PHASE 1 REPORT` counts from the successful real run
2. Freeze Phase 1 if report-level validation is clean
3. Validate the local Bionic / LM Studio endpoint with a minimal Python smoke test
4. Begin Phase 2 Sequential LLM baseline before PURE modules

## Working rule
This file is the authoritative snapshot of current project status. Update it whenever the phase, backend, dataset, model, cleaning policy, or next task changes. Important experiment runs are appended to `EXPERIMENT_LOG.md`; methodology decisions belong in dedicated docs such as `PREPROCESSING_POLICY.md`.
