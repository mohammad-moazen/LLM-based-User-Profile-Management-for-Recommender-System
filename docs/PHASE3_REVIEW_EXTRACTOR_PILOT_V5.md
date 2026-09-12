# Phase 3 PURE Review Extractor — Pilot v5 Result

## Status
**PASS / ACCEPTED FOR FULL EXTRACTION**

This pilot uses the local derivative model `llama-3.2-3b-instruct-uncensored`; it is not an exact run of the paper's `Llama-3.2-3B-Instruct` checkpoint.

## Purpose
Pilot v5 evaluated the evidence-backed Review Extractor with **entry-level conservative grounding filtering**. Each generated entry contains a model interpretation (`value`) plus a purported review quote (`evidence`). Only evidence that is a contiguous span of the canonical review is allowed into the downstream-safe extraction. Unsupported entries are rejected and logged individually rather than invalidating the rest of an otherwise structurally valid response.

## Run summary
- frozen recommendation sessions: 94
- required unique historical review extractions: 134
- pilot requested: 3
- successful extractions: 3
- failed extractions: 0
- users represented: 1
- accepted likes entries: 6
- accepted dislikes entries: 2
- accepted key-feature entries: 3
- rejected unsupported entries: 1
- total generated entries before grounding filter: 12
- rejection rate in this pilot: 1/12 = 8.33%
- total reported tokens: 1,898
- mean latency: 3.999 seconds/extraction
- structured output: evidence-backed JSON Schema
- grounding policy: entry-level verbatim-evidence filter
- generation temperature: 0.0
- generation seed: 42
- max output tokens: 512

## Qualitative inspection
### Review 1
The accepted extraction was review-grounded:
- positive evidence: `It's a wonderful keyboard,`
- negative evidence: the driver's-update warning/occasional breakage span
- no key feature was forced when the review did not support one clearly.

No entry was rejected.

### Review 2
The model generated useful grounded entries for appearance, durability, and gaming features. It also generated one unsupported title-derived claim:

```json
{
  "field": "key_features",
  "value": "backlit",
  "evidence": "rainbow backlit wired gaming keyboard mouse combo",
  "reason": "evidence_not_contiguous_span_of_review"
}
```

That evidence is not present in the review text. The v5 filter rejected only this entry while preserving the three grounded entries from the same response. Therefore title-derived content did not enter the downstream-safe extraction.

### Review 3
All stored profile-safe evidence spans were present in the review and covered build quality/switch experience, LED/backlight behavior, the RGB/color limitation, and configurable LED effects.

A useful implementation caveat remains: the model's audit-only `value` may sometimes be broader or less precisely aligned with its chosen evidence span (for example, a normalized feature label may not itself appear inside the evidence quote). Pilot v5 does **not** trust `value` for profile construction. Only the mechanically validated `evidence` strings are allowed downstream. This keeps the profile conservative while retaining `value` only for inspection/debugging.

Some evidence spans are longer than ideal and can overlap across likes/dislikes/key-features. This is acceptable at this stage because PURE's next component, Profile Updater, is responsible for redundancy/conflict consolidation. No automatic semantic rewrite is performed in Review Extractor.

## Acceptance rationale
Pilot v5 satisfies the active gate:
1. all 3 responses were structurally valid;
2. all stored profile-safe entries were mechanically grounded in the review text;
3. the single unsupported title-derived entry was explicitly rejected and logged;
4. no unsupported evidence survived into the downstream-safe extraction;
5. no future/target review leakage was introduced;
6. the remaining overlap/redundancy is deferred to Profile Updater as intended by the architecture.

Therefore v5 is accepted as the Review Extractor policy for the current local derivative-model experiment.

## Next step
Run all 134 required unique historical reviews using the same v5 schema, prompt, model, generation settings, runtime profile, and output directory with:

- `max_extractions = 0`
- `resume = true`
- `fail_fast = false`

Because the three accepted pilot tasks are already present in `outputs/phase3_review_extractor_v5/`, resume should skip them and process the remaining 131 tasks. Errors, if any, remain retryable on a later resume run.
