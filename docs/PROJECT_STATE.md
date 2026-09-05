# Project State

## Project
Step-by-step Python reproduction of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
Phase 0 / Dataset validation and local inference setup.

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

## Core task definition
For each user, interactions are sorted chronologically. The recommender predicts the next purchased item from a candidate set containing one ground-truth item and 19 randomly sampled non-interacted items. The initial implementation uses `min_history = 3`, so the first prediction target is purchase 4.

## PURE components to reproduce
1. Review Extractor
2. Profile Updater
3. LLM Recommender

## Confirmed full-dataset validation results
- Metadata records: 84,819
- Unique metadata ASINs: 71,911
- Duplicate metadata ASIN rows: 12,908
- Review records: 497,577
- Unique users: 55,217
- Unique reviewed items: 17,408
- Review rows missing required fields: 158
- Review items missing metadata lookup: 1,262
- Review-to-metadata coverage: 99.7464%
- Repeated `(user, item)` rows: 24,149
- Users with >=3 interactions: 55,211
- Users with >=4 interactions: 55,210
- Users with >=5 interactions: 55,200
- Median history length: 6
- Mean history length: 9.01
- Maximum history length: 815

## Data-cleaning decisions not yet frozen
Before implementing the canonical processed dataset, inspect and document:
1. Duplicate metadata ASIN records and how titles differ across duplicates
2. Repeated `(user, item)` review rows and whether they are exact duplicates, repeated purchases, or multiple reviews at different times
3. The 158 review rows missing required fields
4. The 1,262 review rows whose ASIN is absent from the metadata lookup

Cleaning rules must be deterministic, documented, and applied before candidate generation or evaluation.

## Current implementation status
Completed:
- Repository initialization and branch setup
- Dataset schema inspection script
- `.gitignore` protections for dataset/model artifacts
- Full-dataset validation script
- Full Video Games validation run and documentation

Pending next:
1. Inspect dataset anomalies and freeze cleaning rules
2. Implement processed data pipeline
3. Build chronological user histories
4. Build deterministic candidate sampling
5. Implement NDCG metrics and unit tests
6. Validate local LLM endpoint with a minimal Python smoke test
7. Implement Sequential baseline before PURE modules

## Working rule
This file is the authoritative snapshot of current project status. Update it whenever the phase, backend, dataset, model, cleaning policy, or next task changes.
