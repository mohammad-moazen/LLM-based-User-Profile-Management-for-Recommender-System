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

## Pilot v5 grounding policy: entry-level conservative filtering
Pilot v4 demonstrated that one unsupported evidence item should not discard other valid review-grounded entries from the same otherwise-usable response.

Pilot v5 therefore validates each generated entry independently:

1. structural/schema violations still fail the entire response;
2. each `evidence` string is checked against the canonical review after case/whitespace normalization;
3. grounded entries are accepted unchanged;
4. unsupported entries are rejected individually and logged with field, value, evidence, and reason;
5. rejected entries are never rewritten, inferred, replaced, or silently moved to another category;
6. only accepted evidence can enter the downstream-safe profile representation.

This is conservative filtering rather than semantic repair. It is an explicit reproduction engineering choice for the active local derivative model because the paper does not publish an exact grounding validator.

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

### Pilot v5 gate
Pilot v5 reruns the same first three reviews with the same model/generation/runtime settings and entry-level conservative evidence filtering.

Output directory:

`outputs/phase3_review_extractor_v5/`

Checked-in settings:
- `max_extractions = 3`
- `resume = true`
- `fail_fast = true`

Pilot v5 is accepted if all three responses are structurally valid, all profile-safe stored entries are review-grounded, any unsupported generated entries are explicitly logged/rejected, no title-only content survives into the safe extraction, and category assignment is qualitatively reasonable.

After a clean v5 pilot, `max_extractions` can be changed to `0` and `fail_fast` to `false` for all 134 required historical reviews.

## Automatic experiment handoff
The runner publishes a compact result/error payload to `handoff/latest.json` and automatically commits/pushes only that path. This removes the need to paste long terminal outputs into chat. Full experiment artifacts remain local under ignored `outputs/` directories.

After ChatGPT reads a handoff, durable findings are recorded in project docs and the mailbox is reset to `READY` for the next run. See `docs/EXPERIMENT_HANDOFF.md`.

## Relevant files
- `config/phase3_review_extractor.toml`
- `src/pure_recommender/pure/review_extractor.py`
- `src/pure_recommender/experiment_handoff.py`
- `src/pure_recommender/phase3/tasks.py`
- `scripts/run_phase3_review_extractor.py`
- `scripts/inspect_phase3_review_extractor_pilot.py`
- `tests/test_review_extractor.py`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V2.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V3.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V4.md`
- `docs/EXPERIMENT_HANDOFF.md`

## Local outputs
Historical pilot outputs remain untracked under v1-v5 output directories. Each run writes `extractions.jsonl` and `summary.json` locally.
