# Phase 3 PURE Review Extractor Protocol

## Purpose
This stage reproduces **STEP 1: Extract User Representation** from PURE before implementing the Profile Updater and final PURE recommender. It is validated independently and does not produce recommendation NDCG by itself.

## Paper-derived behavior
The PURE paper's Algorithm 1 applies the Review Extractor to the incoming review at each time step. The output representation contains likes, dislikes, and key features; this representation is later concatenated with the prior user profile and passed to the Profile Updater. The paper's Step-1 prompt supplies ASINs, product names, and input reviews in chronological order, and the implementation section reports JSON-schema structured output.

The paper does not publish its exact machine-readable schema or an exact evidence-validation mechanism.

## Incremental and leakage-safe policy
For a frozen recommendation session targeting purchase position `t`, only information observed through `t-1` may be used. Therefore a review is never extracted before its purchase occurs, each canonical review is extracted once per accepted extractor version, historical extraction may be reused in later sessions, and the target review is never available when predicting that same target.

The 94 frozen sessions require 134 unique historical review extractions.

## Active input serialization
Each call processes one canonical incoming interaction, matching Algorithm 1's incremental `E(r_t)` behavior. The LLM receives ASIN, canonical title, rating, and canonical review text.

ASIN, title, and review follow the paper's Step-1 description. Rating is included as an explicit reproduction interpretation because Figure 1 states that PURE incorporates ratings. Metadata remains context only; it is not accepted as independent evidence for a profile entry.

## Evidence-backed v4 output
Pilots v1/v2 showed that prompt-only grounding could still copy title-only attributes. Pilot v3 solved that leakage by requiring every generated string to be an exact review span, but it also rejected a semantically valid paraphrase (`breathing LEDs`) whose source review said the LEDs can `breathe`.

Pilot v4 therefore separates interpretation from evidence. Each category contains objects of the form:

```json
{
  "value": "breathing LEDs",
  "evidence": "LEDs either breathe"
}
```

The full logical structure is:

```json
{
  "likes": [{"value": "...", "evidence": "..."}],
  "dislikes": [{"value": "...", "evidence": "..."}],
  "key_features": [{"value": "...", "evidence": "..."}]
}
```

Rules:
- `value` may be a concise faithful paraphrase/normalization;
- `evidence` must be a short contiguous verbatim span from the source review;
- the parser validates every evidence span after case/whitespace normalization;
- title-only or outside-review evidence is rejected;
- unsupported categories remain empty;
- no semantic repair, inferred evidence, category migration, or deduplication is performed.

For downstream profile construction, the stored safe extraction uses the **verbatim evidence strings**. The model's `value` field is retained separately for audit/inspection only. Redundancy and conflict resolution remain the responsibility of Profile Updater.

This exact schema/evidence mechanism is a reproduction engineering choice because the paper does not publish its JSON schema.

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
Mechanical verbatim grounding blocked title leakage, but was too strict and rejected a legitimate paraphrase (`breathing LEDs`). See `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V3.md`.

### Pilot v4 gate
Pilot v4 reruns the same first three reviews with the same model/generation/runtime settings using the evidence-backed schema.

Output directory:

`outputs/phase3_review_extractor_v4/`

Checked-in settings:
- `max_extractions = 3`
- `resume = true`
- `fail_fast = true`

Pilot v4 is accepted only if all three calls are schema-valid, every evidence field passes exact review-span validation, no title-only attribute can enter the safe extraction, category assignment is reasonable, and no future/target review leakage occurs.

After a clean pilot, `max_extractions` can be changed to `0` and `fail_fast` to `false` for all 134 required historical reviews.

## Automatic experiment handoff
The runner publishes a compact result/error payload to:

`handoff/latest.json`

and automatically commits/pushes only that path. This removes the need to paste long terminal outputs into chat. The handoff mechanism is documented in `docs/EXPERIMENT_HANDOFF.md`. Full experiment artifacts remain local under ignored `outputs/` directories.

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
- `docs/EXPERIMENT_HANDOFF.md`

## Local outputs
Historical pilot outputs remain untracked under v1-v4 output directories. Each accepted run writes `extractions.jsonl` and `summary.json` locally.
