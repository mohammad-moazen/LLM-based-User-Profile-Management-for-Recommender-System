# Phase 3 PURE Review Extractor — Final Results

## Status
**PASS / FROZEN**

This document records the accepted final state of the PURE Review Extractor for the frozen 20-user / 94-session Video Games experiment.

The result uses the local derivative model `llama-3.2-3b-instruct-uncensored`; it is **not** an exact paper-checkpoint reproduction of `Llama-3.2-3B-Instruct`.

## Accepted protocol
The accepted extractor is the v5 evidence-backed protocol with entry-level conservative grounding filtering:

- the model returns `likes`, `dislikes`, and `key_features`;
- each generated entry contains an audit-only concise `value` plus an `evidence` span;
- only evidence mechanically grounded in the canonical review may enter the profile-safe representation;
- unsupported evidence is rejected and logged entry-by-entry;
- blank evidence is rejected as `empty_evidence` rather than failing the whole response;
- rejected entries are never rewritten, inferred, or replaced;
- structural/schema violations still fail the response;
- target/future reviews are never used before they become historical observations.

This exact schema and grounding validator are reproduction engineering choices because the paper does not publish its machine-readable JSON schema or post-processing validator.

## Final complete extraction state
After the resume-only retry of the three blank-evidence failures from full-run attempt 1, all required historical reviews are successful:

| Measure | Final value |
| --- | ---: |
| Required unique extractions | 134 |
| Successful extractions | 134 |
| Failed extractions | 0 |
| Users represented | 20 |
| Accepted likes entries | 236 |
| Accepted dislikes entries | 97 |
| Accepted key-feature entries | 163 |
| Total accepted entries | 496 |
| Rejected unsupported/blank-evidence entries | 36 |
| Total generated entries before grounding filter | 532 |
| Entry rejection rate | 6.77% |
| Prompt tokens | 70,502 |
| Completion tokens | 22,327 |
| Total reported tokens | 92,829 |
| Total successful-request latency | 525.338 s (~8.76 min) |
| Mean latency per extraction | 3.920 s |
| Final status | PASS |

The 36 rejected entries are **not task failures**. They are generated entries that did not satisfy the accepted evidence-grounding policy and were therefore excluded from downstream profile-safe data.

## Retry history
Full-run attempt 1 reached 131/134 successful tasks. The three failures all contained blank `evidence` strings inside otherwise structured outputs. The parser was patched so blank evidence is treated as an individually rejected entry instead of a response-level error. With `resume = true`, the next run skipped the 131 already successful tasks and retried only those three failures.

The resulting combined latest-task state is 134 successful / 0 failed.

## Frozen inputs and generation settings
- frozen Phase 1 sessions: 94
- required unique historical reviews: 134
- model: `llama-3.2-3b-instruct-uncensored`
- temperature: 0.0
- generation seed: 42
- max output tokens: 512
- structured output: evidence-backed JSON Schema
- grounding: entry-level verbatim-evidence filter
- local output directory: `outputs/phase3_review_extractor_v5/`
- runtime profile: the validated stable LM Studio profile documented in `docs/RUNTIME_MEMORY_STABILITY.md`

## Interpretation
The Review Extractor component is now frozen for the current reproduction branch. Downstream Profile Updater work should consume only the accepted `extraction` fields produced by this run, not rejected entries and not audit-only normalized `value` fields.

Long or overlapping evidence spans are intentionally left for the Profile Updater to consolidate, matching the architectural separation between extraction and profile maintenance.

## Related records
- `docs/PHASE3_REVIEW_EXTRACTOR_PROTOCOL.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V2.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V3.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V4.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V5.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_FULL_RUN_ATTEMPT1.md`
