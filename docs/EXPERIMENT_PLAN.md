# Experiment Plan

## Goal
Reproduce PURE incrementally, beginning with a small, fully testable local experiment and expanding toward the paper's continuous sequential recommendation setup and ablations.

## Phase 0 — Environment and validation
- Verify Amazon Video Games 5-core review and metadata files
- Confirm local storage paths
- Configure local LLM runtime
- Test local OpenAI-compatible endpoint
- Record exact model, quantization, context length, and inference settings

## Phase 1 — Data and evaluation pipeline (no LLM dependency)
- Stream/load review data
- Join reviews with metadata by ASIN
- Normalize to canonical interaction schema
- Sort each user's history chronologically
- Enforce configurable `min_history` (initially 3)
- Generate 20-item candidate sets: 1 target + 19 non-interacted negatives
- Make negative sampling deterministic with an explicit seed
- Implement NDCG@1, NDCG@5, NDCG@10, NDCG@20
- Add tests for chronology, leakage prevention, candidate construction, and metrics

## Phase 2 — LLM Sequential baseline
Use purchased-item history and the candidate set only. The local LLM ranks candidate items.

## Phase 3 — Review Extractor + Recommender
- Extract likes, dislikes, and key features from reviews
- Use structured output
- Build recommendation prompts using extracted information
- Initially omit Profile Updater to isolate extractor value and simplify debugging

## Phase 4 — Full PURE
- Maintain evolving user profile
- Merge new representation with the prior profile
- Remove redundant/overlapping/conflicting information
- Track context/token growth and profile size

## Phase 5 — Baselines
- Sequential
- Recency-focused
- In-context learning (ICL)
- Raw-review variants where appropriate for comparison with the paper

## Phase 6 — Continuous sequential evaluation and ablation
- Predict at every eligible timestep
- Aggregate NDCG within each user across recommendation sessions
- Average user-level scores across users
- Ablate reviews, extractor, and updater
- Record recommendation input token lengths

## Phase 7 — Scale-up
- Start with a small deterministic user subset (e.g. 20 users)
- Expand gradually: 50 -> 100 -> 500 -> larger/full feasible evaluation
- Repeat on Movies & TV only after Video Games pipeline is stable

## Phase 8 — Model comparison (secondary research extension)
After the Llama reproduction is stable, optionally compare PURE across additional local models such as a suitable Qwen model. This phase must not contaminate the baseline reproduction.

## Reproducibility requirements
Every experiment must record at least:
- Git commit SHA
- dataset/category
- subset selection rule and seed
- number of users/interactions/sessions
- model identifier
- quantization
- context length
- temperature and other generation settings
- candidate sampling seed
- PURE/baseline configuration
- NDCG metrics
- runtime notes and failures

## Important paper-alignment note
The paper's problem formulation and experiment wording differ slightly around the first eligible continuous prediction timestep. Our implementation therefore keeps `min_history` configurable. The initial setting is `min_history = 3`, corresponding to predicting purchase 4 from purchases 1–3, matching the experiment description.
