# Project State

## Project
Step-by-step Python reproduction of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
Phase 0 complete for dataset inspection/validation; moving into Phase 1 canonical data pipeline. Local inference setup remains pending in parallel.

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

## Confirmed full-dataset validation results
- Metadata records: 84,819
- Unique metadata ASINs: 71,911
- Duplicate metadata ASINs: 12,908
- Duplicate metadata ASIN groups with conflicting non-empty titles: 0
- Review records: 497,577
- Unique users: 55,217
- Unique reviewed items: 17,408
- Review rows missing required fields: 158
- Review rows without usable metadata title: 1,262 across 19 ASINs
- Review-to-metadata coverage: 99.7464%
- Unique `(user, item)` pairs: 473,427
- Repeated `(user, item)` pairs: 23,937
- Repeated pairs identical on PURE-relevant fields: 23,361
- Repeated pairs with different timestamp: 389
- Repeated pairs with different review text: 539
- Repeated pairs with different rating: 133
- Users with >=3 raw interactions: 55,211
- Users with >=4 raw interactions: 55,210
- Users with >=5 raw interactions: 55,200
- Median raw history length: 6
- Mean raw history length: 9.01
- Maximum raw history length: 815

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
8. For candidate sampling, use one target plus 19 negatives sampled without replacement from valid-title items the user never interacts with anywhere in the cleaned full history; use a recorded deterministic seed and shuffle candidate order deterministically.

Important provenance rule: these edge-case cleaning decisions are part of this reproduction. The paper does not document them, so they must never be attributed to the paper authors.

## Current implementation status
Completed:
- Repository initialization and branch setup
- Dataset schema inspection script
- `.gitignore` protections for dataset/model artifacts
- Full-dataset validation script
- Full Video Games validation run and documentation
- Dataset anomaly analysis
- Frozen preprocessing policy v1
- Documentation framework: `PROJECT_STATE.md`, `EXPERIMENT_PLAN.md`, `EXPERIMENT_LOG.md`, `PREPROCESSING_POLICY.md`

Pending next:
1. Implement canonical processed-data pipeline according to preprocessing-policy v1
2. Run pipeline locally and record post-cleaning counts
3. Build chronological user histories and deterministic small-user subset selection
4. Build deterministic candidate sampling
5. Implement NDCG metrics and unit tests
6. Validate local LLM endpoint with a minimal Python smoke test
7. Implement Sequential baseline before PURE modules

## Working rule
This file is the authoritative snapshot of current project status. Update it whenever the phase, backend, dataset, model, cleaning policy, or next task changes. Important experiment runs are appended to `EXPERIMENT_LOG.md`; methodology decisions belong in dedicated docs such as `PREPROCESSING_POLICY.md`.
