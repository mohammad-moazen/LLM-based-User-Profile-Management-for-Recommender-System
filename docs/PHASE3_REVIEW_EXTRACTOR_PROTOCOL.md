# Phase 3 PURE Review Extractor Protocol

## Purpose
This stage reproduces **STEP 1: Extract User Representation** from PURE before implementing the Profile Updater and final PURE recommender.

The stage is intentionally validated independently first. It does **not** produce recommendation NDCG by itself.

## Paper-derived behavior
The PURE paper's Algorithm 1 applies the Review Extractor to the incoming review at each time step:

- extractor input: the incoming review `r_t` associated with the purchased item;
- extracted representation: likes, dislikes, and key features;
- the extracted representation is later concatenated with the previous profile and passed to the Profile Updater;
- the paper's Step-1 prompt supplies ASINs, product names, and input reviews in chronological order and asks the LLM to analyze likes, dislikes, and key features;
- Figure 1 states that PURE incorporates reviews, ratings, and item interactions;
- the implementation section states that JSON schemas are used for structured LLM outputs.

The paper does not publish the exact machine-readable JSON schema or an exact evidence-validation mechanism.

## Incremental extraction policy
For the frozen continuous-recommendation experiment, a recommendation session targeting purchase position `t` may use only information observed through `t-1`.

Therefore:

1. A review is never extracted before its corresponding purchase has occurred.
2. Each canonical review is extracted at most once per accepted extractor version.
3. Once a purchase/review becomes historical context for a later session, its extraction may be reused by the evolving profile.
4. The current target review is never available to the profile used to predict that same target.

The workload is derived from the already frozen Phase 1 sessions rather than from future interactions outside those sessions.

## Active prompt serialization
Each extractor call processes one chronological incoming interaction, matching Algorithm 1's `E(r_t)` update pattern.

The LLM receives:

- ASIN;
- canonical product title;
- rating;
- canonical review text.

ASIN, product name, and review text follow the Step-1 prompt description. Rating is included because Figure 1 explicitly states that PURE incorporates ratings. The paper does not clarify whether rating is implicitly part of the `input reviews` placeholder, so including it as a separate field is an explicit reproduction interpretation and must not be attributed as an exact published prompt string.

Unlike the Phase 2 ranking baselines, ASIN is intentionally visible here because the paper explicitly includes ASINs in the Review Extractor input.

## Review-grounding policy
Two pilot rounds showed that prompt-only instructions were insufficient for the active local derivative model: it could still copy or infer title-only attributes into `key_features` even when the review did not mention them.

The accepted-candidate v3 protocol therefore uses a stronger deterministic rule:

- ASIN and product title identify the purchased product but are not independent evidence;
- rating provides sentiment context but is not independent evidence for a specific attribute;
- every returned string in `likes`, `dislikes`, and `key_features` must be a **short contiguous verbatim span from the review text**;
- the local parser checks every generated entry against the canonical review after case/whitespace normalization;
- title-only, inferred, or paraphrased entries are rejected rather than silently filtered or repaired;
- unsupported categories remain empty.

This verbatim-span rule is an explicit reproduction engineering choice introduced to operationalize the paper's review-focused extractor reliably with the current local model.

## Structured output schema
The logical output remains:

```json
{
  "likes": ["..."],
  "dislikes": ["..."],
  "key_features": ["..."]
}
```

All three keys are required. Each value is an array of strings and may be empty.

This exact schema is a reproduction choice. The paper reports JSON-schema structured outputs but does not publish the schema itself.

The local OpenAI-compatible client supports a pass-through `response_format`, and the Review Extractor requests a strict JSON Schema from LM Studio. A local parser validates both structure and review grounding after generation.

## No silent semantic repair
The extractor parser:

- rejects missing or unexpected keys;
- rejects non-array categories;
- rejects non-string or blank entries;
- rejects entries that are not verbatim spans of the source review when production grounding validation is enabled;
- does not invent missing preferences;
- does not move entries between categories;
- does not deduplicate model output.

Redundancy and conflict resolution remain the responsibility of the Profile Updater.

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
Technical PASS, but qualitative inspection found title-only attributes copied into `key_features` for the first two reviews.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`.

### Pilot v2
Technical PASS, but semantic grounding was still insufficient. Review 2 still produced title-derived `backlit keyboard` and `wired mouse`; Review 1 also showed category overlap/rephrasing in key features.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V2.md`.

### Pilot v3 gate
Pilot v3 reruns the same first three reviews with the same model/generation/runtime settings but adds mandatory verbatim-span validation.

Output directory:

`outputs/phase3_review_extractor_v3/`

Checked-in configuration:
- `max_extractions = 3`
- `resume = true`
- `fail_fast = true`

Pilot v3 is accepted only if:

1. all 3 calls return schema-valid outputs;
2. every stored entry passes mechanical verbatim-review grounding;
3. no title-only/inferred feature survives validation;
4. no future/target review is used early;
5. qualitative category assignment is reasonable enough to proceed to full extraction.

After a clean v3 pilot, `max_extractions` can be changed to `0` and `fail_fast` to `false` to process all 134 unique historical reviews.

## Relevant files
- `config/phase3_review_extractor.toml`
- `src/pure_recommender/pure/review_extractor.py`
- `src/pure_recommender/phase3/config.py`
- `src/pure_recommender/phase3/tasks.py`
- `scripts/run_phase3_review_extractor.py`
- `scripts/inspect_phase3_review_extractor_pilot.py`
- `tests/test_review_extractor.py`
- `tests/test_phase3_review_tasks.py`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`
- `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V2.md`

## Local outputs
Historical pilot outputs remain untracked under:

- `outputs/phase3_review_extractor/` — v1
- `outputs/phase3_review_extractor_v2/` — v2
- `outputs/phase3_review_extractor_v3/` — v3

Expected files in each output directory:

- `extractions.jsonl`
- `summary.json`
