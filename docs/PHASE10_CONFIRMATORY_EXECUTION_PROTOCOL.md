# Phase 10 — Confirmatory Execution Protocol

## Purpose

Phase 10 executes the prospective 150-user confirmatory study that was designed and frozen in Phases 8–9. The required primary comparison remains **PURE vs Recency-Focused on NDCG@10**, with alpha 0.05, two-sided, and equal-user aggregation.

The original 20-user pilot is not rerun and is not pooled into the confirmatory hypothesis test.

## Immutable Phase 9 inputs

Every Phase 10 stage must verify the Phase 9 freeze before its first model call:

- users: 150 new users
- recommendation sessions: 767
- profile evidence events: 1,067
- cohort SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- sessions/candidates SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

No Phase 10 runner may regenerate, reorder, replace, filter, or outcome-select users or candidate sets.

## Runtime decision

Phase 10A tested two concurrent predictions before any confirmatory outcome was observed. Two workers produced a 2.1475x synthetic throughput speedup but only 5/8 exact output matches relative to sequential execution. Because exact repeatability was a pre-declared acceptance requirement, the two-worker runtime was rejected.

The confirmatory runtime therefore uses the accepted one-worker profile:

- Context Length: 8192
- Max Concurrent Predictions: **1**
- Evaluation Batch: 512
- Physical Batch: 256
- CPU threads: 7
- GPU Offload: maximum/all layers
- Unified KV: ON
- KV cache on GPU: ON
- Flash Attention: ON
- K/V cache quantization: OFF
- speculative decoding: OFF
- keep model in memory: ON
- mmap: ON

Generation settings remain the same as the frozen pilot for corresponding components: temperature 0.0, seed 42, recommender max output 512, Review Extractor/Profile Updater max output 1024.

## Stage plan

Phase 10 is executed in auditable stages so long local runs can be reviewed before dependent stages begin.

### Phase 10B1 — Review Extractor

- consumes Phase 1 canonical interactions plus the frozen Phase 9 sessions;
- requires exactly 1,067 unique historical review extractions;
- target/future reviews remain invisible before purchase;
- uses the accepted evidence-backed structured output and entry-level verbatim grounding filter;
- resume is enabled for interruption recovery;
- output: `outputs/phase10_confirmatory_review_extractor_v1/`.

### Phase 10B2 — Profile Updater

- consumes only accepted Phase 10B1 extraction rows;
- preserves chronological within-user dependency;
- uses the accepted v4 information-preserving dominance guard;
- expected updates: 1,067;
- output directory will be versioned separately.

### Phase 10B3 — Recency-Focused baseline

- consumes the immutable 767 Phase 9 sessions;
- no review/profile information is used;
- uses the frozen direct-ranking plus structural fallback contract;
- output directory will be versioned separately.

### Phase 10B4 — PURE recommender

- consumes the immutable 767 Phase 9 sessions and the accepted Phase 10B2 profile states;
- profile alignment remains target-position-minus-one;
- uses the frozen hybrid direct-ranking to rank-map fallback policy;
- output directory will be versioned separately.

### Phase 10C — Confirmatory statistical analysis

The primary statistical unit is the user. Session NDCG@10 values are averaged within each user, then PURE-minus-Recency user differences are analyzed under the pre-declared two-sided alpha 0.05 test/interval procedure. The result is reported regardless of direction or significance.

## Anti-p-hacking rule

Once Phase 10B1 begins, runtime, endpoint, cohort, sessions, candidate order, prompts, output-validation policy, primary metric, and primary comparison are not changed based on confirmatory effectiveness results. Any such change would require a separately labeled experiment version rather than replacement of this study.
