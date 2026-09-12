# Phase 3 PURE Review Extractor Protocol

## Purpose
This stage reproduces **STEP 1: Extract User Representation** from PURE before implementing the Profile Updater and final PURE recommender. It is validated independently and does not produce recommendation NDCG by itself.

## Paper-derived behavior
The PURE paper's Algorithm 1 applies the Review Extractor to the incoming review at each time step. The output representation contains likes, dislikes, and key features; this representation is later concatenated with the prior user profile and passed to the Profile Updater. The paper's Step-1 prompt supplies ASINs, product names, and input reviews in chronological order, and the implementation section reports JSON-schema structured output.

The paper does not publish its exact machine-readable schema or an exact evidence-validation/post-processing mechanism.

## Incremental and leakage-safe policy
For a frozen recommendation session targeting purchase position `t`, only information observed through `t-1` may be used. A review is never extracted before its purchase occurs, historical extraction may be reused in later sessions, and the target review is never available when predicting that same target.

The 94 frozen sessions require 134 unique historical review extractions.

## Active input serialization
Each call processes one canonical incoming interaction, matching Algorithm 1's incremental `E(r_t)` behavior. The LLM receives ASIN, canonical title, rating, and canonical review text.

ASIN, title, and review follow the paper's Step-1 description. Rating is included as an explicit reproduction interpretation because Figure 1 states that PURE incorporates ratings. Metadata remains context only; it is not accepted as independent evidence for a profile entry.

## Evidence-backed output
Pilots v1/v2 showed title leakage. Pilot v3 used exact-review-span outputs and became too restrictive for legitimate paraphrases. Pilot v4 separated model interpretation from exact evidence, but the derivative local model still fabricated one evidence span from the visible product title.

The logical model output therefore remains evidence-backed:

```json
{
  "likes": [{"value": "...", "evidence": "..."}],
  "dislikes": [{"value": "...", "evidence": "..."}],
  "key_features": [{"value": "...", "evidence": "..."}]
}
```

Rules:
- `value` may be a concise faithful paraphrase/normalization;
- `evidence` is intended to be a short contiguous verbatim span from the source review;
- the model's `value` field is retained for audit only;
- downstream profile input uses only validated review evidence strings;
- redundancy/conflict handling remains the responsibility of Profile Updater.

## Accepted grounding policy: entry-level conservative filtering
The accepted v5 policy validates each generated entry independently:

1. structural/schema violations fail the entire response;
2. non-empty `evidence` strings are checked against the canonical review after case/whitespace normalization;
3. grounded entries are accepted unchanged;
4. unsupported entries are rejected individually and logged with field, value, evidence, and reason;
5. blank evidence is rejected individually with reason `empty_evidence`;
6. rejected entries are never rewritten, inferred, replaced, or silently moved to another category;
7. only accepted evidence can enter the downstream-safe profile representation.

The JSON schema now asks for non-empty `value` and `evidence` strings (`minLength = 1`), and the prompt explicitly instructs the model to omit unsupported entries instead of returning blank evidence. The local validator still treats any blank evidence that slips through as rejected profile data rather than a response-level failure.

This is conservative filtering rather than semantic repair. It is an explicit reproduction engineering choice for the active local derivative model because the paper does not publish an exact grounding validator.

A known limitation is that the audit-only `value` can occasionally be broader or less precisely aligned with its selected evidence span. Because `value` is not used for profile construction, this cannot inject unsupported content into the downstream-safe profile. Some accepted evidence spans may also be longer than ideal or overlap categories; Profile Updater is responsible for later consolidation.

## Frozen experimental basis
- Dataset: Amazon Review Data 2018 / Video Games 5-core
- frozen users: 20
- frozen recommendation sessions: 94
- required unique historical review extractions: 134
- canonical preprocessing: Phase 1 policy v1
- active model: `llama-3.2-3b-instruct-uncensored`
- result label: local derivative-model result; not exact paper-checkpoint reproduction
- temperature: 0.0
- generation seed: 42
- max extractor output tokens: 512
- local runtime: validated stable LM Studio profile in `docs/RUNTIME_MEMORY_STABILITY.md`

## Pilot history
### Pilot v1
Technical PASS, but title-only attributes were copied into `key_features` for the first two reviews. See `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`.

### Pilot v2
Technical PASS, but stronger prompt-only grounding still allowed title-derived attributes. See `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V2.md`.

### Pilot v3
Mechanical verbatim grounding blocked title leakage but rejected a legitimate paraphrase. See `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V3.md`.

### Pilot v4
Evidence-backed schema worked for the first review, but Review 2 included an unsupported title-derived evidence claim (`rainbow backlit wired gaming keyboard mouse combo`). The deterministic validator caught it and fail-fast stopped before Review 3. See `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V4.md`.

### Pilot v5 — PASS / accepted
The same three reviews were processed successfully with the entry-level conservative filter:
- 3/3 successful extractions;
- 0 failed extractions;
- 6 accepted likes entries;
- 2 accepted dislikes entries;
- 3 accepted key-feature entries;
- 1 unsupported entry explicitly rejected;
- 1,898 total reported tokens;
- 3.999 seconds mean latency.

The rejected entry was the title-derived `backlit` claim from Review 2. It was logged and excluded while the grounded entries from the same response were preserved. No unsupported evidence entered the downstream-safe extraction.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V5.md`.

## Full extraction run — attempt 1
The accepted v5 policy was run across all 134 required unique historical reviews.

Result:
- successful extractions: 131
- failed extractions: 3
- accepted likes: 224
- accepted dislikes: 95
- accepted key features: 156
- unsupported generated entries rejected safely: 34
- total reported tokens: 90,055
- mean successful-request latency: 3.848 seconds
- total successful-request latency: 504.068 seconds (~8.40 minutes)
- status: INCOMPLETE

All three failures had the same cause: a generated `key_features` entry had `evidence: ""`. The parser previously treated blank evidence as a response-level validation error before entry-level filtering could run. The retry patch now rejects a blank-evidence entry individually with reason `empty_evidence`, preserving other grounded entries in that response.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_FULL_RUN_ATTEMPT1.md`.

The accepted v5 directory remains unchanged and `resume = true` remains enabled. Therefore the next run should skip the 131 successful tasks and retry only the 3 failed tasks.

The Review Extractor is not frozen until the complete state reaches 134 successful / 0 failed and final rejection statistics are recorded.

## Automatic experiment handoff
The runner publishes a compact result/error payload to `handoff/latest.json` and automatically commits/pushes only that path. This removes the need to paste long terminal outputs into chat. Full experiment artifacts remain local under ignored `outputs/` directories.

After ChatGPT reads a handoff, durable findings are recorded in project docs and the mailbox is reset to `READY` for the next run. See `docs/EXPERIMENT_HANDOFF.md`.

For fatal wrapper-level exceptions, `scripts/run_phase3_review_extractor_safe.py` also captures and publishes the Python traceback so terminal traceback copying is unnecessary.

## Relevant files
- `config/phase3_review_extractor.toml`
- `src/pure_recommender/pure/review_extractor.py`
- `src/pure_recommender/experiment_handoff.py`
- `src/pure_recommender/phase3/tasks.py`
- `scripts/run_phase3_review_extractor.py`
- `scripts/run_phase3_review_extractor_safe.py`
- `scripts/inspect_phase3_review_extractor_pilot.py`
- `tests/test_review_extractor.py`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V2.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V3.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V4.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V5.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_FULL_RUN_ATTEMPT1.md`
- `docs/EXPERIMENT_HANDOFF.md`

## Local outputs
Historical pilot outputs remain untracked under v1-v5 output directories. The accepted-v5 directory is reused with `resume = true` so successful tasks are not recomputed during retry.
