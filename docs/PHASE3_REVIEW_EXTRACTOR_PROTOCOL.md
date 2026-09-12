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

The paper does not publish the exact machine-readable JSON schema.

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

### Review-grounding policy
The first three-review real-data pilot showed that the local derivative model could copy attributes from the product title into `key_features` even when the review never discussed them. Because the published Step-1 instruction asks the LLM to analyze preferences by referring to the reviews, the accepted reproduction prompt now applies a stricter semantic rule:

- ASIN and product title identify the purchased product but are not independent evidence for a preference or key feature;
- rating provides overall sentiment context but is not independent evidence for a specific attribute;
- every entry in `likes`, `dislikes`, and `key_features` must be supported by the review text itself;
- a product-title attribute may appear in the extraction only when the review also explicitly mentions or clearly describes it;
- unsupported categories should remain empty rather than being filled from title/catalog context.

This exact grounding instruction is a reproduction choice introduced to operationalize the paper's review-focused extractor with the current local derivative model.

## Structured output schema
The project uses the following logical object:

```json
{
  "likes": ["..."],
  "dislikes": ["..."],
  "key_features": ["..."]
}
```

All three keys are required. Each value is an array of strings and may be empty if the review provides no supported evidence for that category.

This exact schema is a reproduction choice. The paper reports JSON-schema structured outputs but does not publish the schema itself.

The local OpenAI-compatible client supports a pass-through `response_format`, and the Review Extractor requests a strict JSON Schema from LM Studio. A local parser still validates the response after generation.

## No silent semantic repair
The extractor parser:

- rejects missing or unexpected keys;
- rejects non-array categories;
- rejects non-string or blank entries;
- does not invent missing preferences;
- does not move entries between categories;
- does not deduplicate model output.

Redundancy and conflict resolution are deliberately deferred to the Profile Updater because that separation is part of PURE's architecture.

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

## Pilot v1 result
The first three-review pilot was technically successful:

- 3/3 schema-valid extractions;
- 0 failed calls;
- total reported tokens: 1,063;
- mean latency: 2.109 seconds.

However, qualitative inspection found title-only attributes in `key_features` for the first two reviews. Pilot v1 is therefore recorded as **technical PASS / semantic refinement required**, not as the accepted extraction set.

Detailed record: `docs/PHASE3_REVIEW_EXTRACTOR_PILOT_V1.md`.

## Pilot v2 gate
The revised prompt is rerun on the exact same three reviews into a fresh directory:

`outputs/phase3_review_extractor_v2/`

The checked-in configuration remains deliberately limited to:

- `max_extractions = 3`
- `resume = true`
- `fail_fast = true`

Pilot v2 is accepted only if:

1. all 3 calls return schema-valid outputs;
2. extracted likes/dislikes/key features are grounded in the review text;
3. title-only attributes are not copied into `key_features` unless also supported by the review;
4. no future/target review is used early;
5. the local server remains stable with the finalized runtime profile.

After a clean v2 pilot, `max_extractions` can be changed to `0` and `fail_fast` to `false` to extract every one of the 134 unique historical reviews required by the 94 frozen sessions.

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

## Local outputs
Historical pilot v1 artifacts remain untracked under:

`outputs/phase3_review_extractor/`

Accepted-candidate pilot v2 artifacts are written under:

`outputs/phase3_review_extractor_v2/`

Expected files in each output directory:

- `extractions.jsonl`
- `summary.json`
