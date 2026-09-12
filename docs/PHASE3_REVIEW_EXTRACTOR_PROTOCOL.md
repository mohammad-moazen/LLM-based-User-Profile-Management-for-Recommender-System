# Phase 3 PURE Review Extractor Protocol

## Purpose
This stage reproduces **STEP 1: Extract User Representation** from PURE before Profile Updater and the final PURE recommender.

## Paper-derived behavior
Algorithm 1 applies Review Extractor to the incoming review at each time step. The extracted representation contains likes, dislikes, and key features and is later concatenated with the prior user profile. The paper's Step-1 prompt supplies ASINs, product names, and input reviews and reports JSON-schema structured outputs.

The paper does not publish its exact machine-readable schema or evidence-validation/post-processing mechanism.

## Incremental and leakage-safe policy
For a recommendation target at position `t`, only information observed through `t-1` may be used. A review is never extracted before its purchase occurs, historical extraction may be reused in later sessions, and the target review is never available when predicting that target.

The 94 frozen sessions require 134 unique historical review extractions.

## Input serialization
Each call processes one canonical incoming interaction, matching Algorithm 1's incremental `E(r_t)` behavior. The model receives ASIN, canonical title, rating, and canonical review text.

ASIN, title, and review follow the paper's Step-1 description. Rating inclusion is an explicit reproduction interpretation based on Figure 1. Metadata is context only and is never accepted as independent profile evidence.

## Evidence-backed output
The project-defined structured output is:

```json
{
  "likes": [{"value": "...", "evidence": "..."}],
  "dislikes": [{"value": "...", "evidence": "..."}],
  "key_features": [{"value": "...", "evidence": "..."}]
}
```

`value` is retained for audit only. `evidence` must be a review-grounded contiguous span, and only validated evidence enters the downstream-safe `extraction` object.

## Conservative grounding policy
Each entry is validated independently:
1. structural/schema violations fail the response;
2. non-empty evidence is checked against canonical review text after case/whitespace normalization;
3. grounded entries are preserved;
4. unsupported entries are rejected/logged individually;
5. blank evidence is rejected with reason `empty_evidence`;
6. rejected entries are never rewritten, inferred, replaced, or moved;
7. only accepted evidence enters downstream profile construction.

This is an explicit reproduction engineering choice because the paper does not publish an exact grounding validator.

## Development history
- Pilot v1: title-only leakage observed.
- Pilot v2: stronger prompt still allowed title-derived content.
- Pilot v3: exact-span-only representation was too restrictive.
- Pilot v4: evidence-backed schema caught unsupported evidence but failed whole response.
- Pilot v5: entry-level conservative filtering accepted.
- Historical `outputs/phase3_review_extractor_v5/`: reached 134/134 after resume/retry but is a development artifact because prompt/schema behavior changed during construction.
- Clean 512-token attempt: 133/134; one long structured response was malformed.
- Failed-task diagnostic at 1024 tokens: PASS, `finish_reason=stop`, 495 completion tokens.

## Final homogeneous experimental basis
- Dataset: Amazon Review Data 2018 / Video Games 5-core
- frozen users: 20
- frozen sessions: 94
- required unique extractions: 134
- active local model: `llama-3.2-3b-instruct-uncensored`
- label: local derivative model, not exact paper checkpoint reproduction
- temperature: 0.0
- seed: 42
- max output tokens: 1024
- runtime: Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1
- final output directory: `outputs/phase3_review_extractor_final_1024/`

## Final homogeneous result — PASS / FROZEN
All 134 required reviews were regenerated from scratch under one unchanged final prompt/schema/parser and one finalized runtime/generation profile.

- successful: 134/134
- failed: 0
- users represented: 20
- accepted likes: 240
- accepted dislikes: 98
- accepted key features: 152
- accepted entries: 490
- rejected unsupported/blank entries: 45
- generated entries before filter: 535
- rejection rate: 8.41%
- prompt tokens: 74,956
- completion tokens: 22,394
- total tokens: 97,350
- total latency: 724.650 s (~12.08 min)
- mean latency: 5.408 s/extraction
- status: PASS / FROZEN

The 45 rejected entries are conservative-filter events, not task failures, and never enter the downstream-safe representation.

Final thesis-grade record: `docs/PHASE3_REVIEW_EXTRACTOR_FINAL_HOMOGENEOUS_RESULTS.md`.

## Frozen downstream contract
Profile Updater must consume only successful `extraction` objects from:

`outputs/phase3_review_extractor_final_1024/extractions.jsonl`

It must not substitute audit-only `value` fields, rejected entries, raw responses, or historical development artifacts for profile-safe evidence.

## Relevant files
- `config/phase3_review_extractor.toml`
- `src/pure_recommender/pure/review_extractor.py`
- `scripts/run_phase3_review_extractor.py`
- `scripts/run_phase3_review_extractor_safe.py`
- `tests/test_review_extractor.py`
- `docs/PHASE3_REVIEW_EXTRACTOR_FINAL_HOMOGENEOUS_RESULTS.md`
