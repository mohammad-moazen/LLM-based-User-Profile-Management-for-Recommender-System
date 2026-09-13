# Phase 10B1 — Confirmatory Review Extractor Results

## Status

**PASS / FROZEN**

Phase 10B1 processed the frozen 150-user confirmatory cohort and completed every historical Review Extractor task required by the 767 immutable Phase 9 recommendation sessions.

## Frozen design verification

- confirmatory users: **150**
- frozen recommendation sessions: **767**
- cohort SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- sessions/candidates SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`
- runtime Max Concurrent Predictions: **1**

Both Phase 9 fingerprints were verified before the confirmatory extractor was delegated to the accepted Phase 3 implementation.

## Generation and validation

- model: `llama-3.2-3b-instruct-uncensored`
- model alignment: local derivative model, not the exact paper checkpoint
- temperature: **0.0**
- generation seed: **42**
- max output tokens: **1024**
- output contract: evidence-backed JSON schema
- grounding validation: entry-level verbatim evidence filter

The prompt, parser, grounding policy, and generation configuration are the same accepted extractor protocol used for the frozen pilot; only the frozen confirmatory workload differs.

## Execution result

- required unique extractions: **1,067**
- successful extractions: **1,067**
- failed extractions: **0**
- users represented: **150**
- status: **PASS**

Accepted profile evidence entries:

- likes: **1,895**
- dislikes: **783**
- key features: **1,309**
- total accepted entries: **3,987**
- rejected unsupported entries: **263**

The 263 rejected entries were filtered by the same entry-level grounding safeguard and were not allowed into downstream profile construction.

## Usage and runtime

- prompt tokens: **581,301**
- completion tokens: **175,122**
- total tokens: **756,423**
- total LLM latency: **4,103.018 s** (~68.38 min)
- mean latency per extraction: **3.845 s**

## Authoritative local artifact

`outputs/phase10_confirmatory_review_extractor_v1/extractions.jsonl`

Downstream Phase 10 profile construction must consume only the successful `extraction` objects from this artifact. The original 20-user pilot extractor artifact remains separate and must not be mixed into the confirmatory cohort.

## Scientific status

This stage does not yet evaluate recommendation effectiveness and does not alter the pre-declared primary hypothesis. It creates the frozen confirmatory evidence stream required by PURE. The primary confirmatory comparison remains **PURE vs Recency-Focused at user-level NDCG@10, alpha 0.05 two-sided**.
