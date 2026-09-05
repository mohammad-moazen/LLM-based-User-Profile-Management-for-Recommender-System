# Preprocessing Policy

## Status
Frozen policy: **v1** for the initial Video Games reproduction.

This document records our explicit preprocessing decisions for Amazon Review Data 2018 / Video Games 5-core. The PURE paper states that user reviews and purchased items are chronologically sorted and used for sequential recommendation, but it does **not** specify how duplicate metadata rows, repeated `(user, item)` review rows, missing review text, or missing product titles were handled. Therefore, the rules below are our deterministic reproduction policy and must not be presented as undocumented choices made by the paper authors.

## Raw inputs
- Reviews: `Video_Games_5.json.gz`
- Metadata: `meta_Video_Games.json.gz`

## Canonical interaction fields
- `user_id` <- `reviewerID`
- `asin`
- `title` <- metadata join on `asin`
- `review_text` <- `reviewText`
- `rating` <- `overall`
- `timestamp` <- `unixReviewTime`

A temporary `source_row_index` may be retained during preprocessing only to provide a deterministic tie-breaker for interactions with the same timestamp. It is not part of the final experiment schema.

## 1. Metadata policy
Observed:
- 84,819 metadata rows
- 71,911 unique ASINs
- 12,908 ASINs occur more than once
- 0 duplicate ASIN groups contain more than one distinct non-empty title
- 11 rows have an empty/invalid title

Rules:
1. Strip surrounding whitespace from `asin` and `title`.
2. Reject metadata rows with an empty/invalid ASIN.
3. Group metadata rows by ASIN.
4. For each ASIN, keep one deterministic record with a non-empty title when available.
5. Duplicate rows with the same usable title are collapsed to one item record.
6. If an ASIN has no usable title after deduplication, it is not eligible for the canonical interaction dataset or candidate pool.
7. Only `asin` and `title` are required in Phase 1; other metadata fields are not used by the initial reproduction.

Rationale: the anomaly analysis found no conflicting non-empty titles among duplicate ASIN groups, so metadata deduplication does not require semantic conflict resolution.

## 2. Review required-field policy
Required fields for the initial PURE reproduction:
- `reviewerID`
- `asin`
- `reviewText`
- `overall`
- `unixReviewTime`

Observed:
- 497,577 review rows
- 158 rows are missing at least one required PURE field
- examples show missing `reviewText`

Rules:
1. Drop rows missing any required field.
2. Do not synthesize `reviewText` from `summary` in the baseline reproduction.
3. Strip only surrounding whitespace from user and item identifiers and review text; do not rewrite, summarize, translate, spell-correct, or otherwise normalize review semantics during preprocessing.

Rationale: PURE explicitly relies on review text. Replacing missing review text with another field would introduce an undocumented transformation.

## 3. Review-to-metadata join policy
Observed:
- 1,262 review rows have no usable product title in metadata
- these misses correspond to only 19 unique ASINs
- title coverage is 99.7464%

Rules:
1. Join reviews to the deduplicated metadata table by ASIN.
2. Drop review interactions whose ASIN has no usable title.
3. Exclude those ASINs from the candidate item universe.
4. Record the number of dropped rows and unique ASINs in every preprocessing run.

Rationale: the paper's Review Extractor prompt uses ASIN/product names/reviews, and recommendation candidates require a stable product representation. Keeping title-less interactions would create a different prompt regime for a very small minority of rows.

## 4. Repeated `(user, item)` policy
Observed:
- 473,427 unique `(user, item)` pairs before cleaning
- 23,937 pairs occur more than once
- 24,150 rows are beyond the first occurrence
- 23,361 repeated pairs are identical on the fields relevant to PURE
- 389 repeated pairs differ in timestamp
- 539 repeated pairs differ in review text
- 133 repeated pairs differ in rating

The raw review dataset does not establish that multiple review rows for the same `(user, item)` are separate purchase events. Treating every repeated review row as a new purchase could therefore create unsupported sequential interactions.

Rules:
1. Compare repeated rows using the PURE-relevant fields: `timestamp`, `rating`, and normalized `review_text`.
2. If all rows in a repeated `(user, item)` group are identical on those fields, collapse the group to one interaction.
3. If a repeated `(user, item)` group contains a conflict in timestamp, rating, or review text, classify the pair as **ambiguous** and exclude all rows for that pair from the canonical v1 dataset.
4. Log counts of collapsed duplicate groups and excluded ambiguous groups/rows.
5. Preserve raw files unchanged so an alternative policy can be tested later as a sensitivity analysis.

Rationale: this is deliberately conservative. It avoids inventing repeated purchase events or arbitrarily choosing one of several conflicting reviews. The ambiguous subset is small relative to the full dataset.

## 5. Chronology policy
1. Sort each user's cleaned interactions by ascending `timestamp`.
2. When two distinct items have the same timestamp, preserve raw-file order using `source_row_index` as the secondary sort key.
3. Never use future interactions to construct a user's observed history at a prediction timestep.
4. The initial task uses `min_history = 3`, so the first target is the fourth cleaned interaction.

The paper states that interactions are chronologically sorted but does not document a same-timestamp tie-breaking rule. The source-row tie-breaker is therefore an explicit reproducibility choice.

## 6. Post-cleaning eligibility
1. Do **not** run a new iterative 5-core filtering pass after cleaning.
2. Determine evaluation eligibility from the cleaned canonical history.
3. A user needs at least `min_history + 1` cleaned interactions to contribute at least one recommendation session. With the initial `min_history = 3`, this means at least 4 cleaned interactions.
4. Users can contribute multiple sessions in continuous sequential evaluation, one for each eligible next-item target.

Rationale: re-running k-core filtering would change the supplied dataset substantially and is not documented in the paper. The task itself only requires enough chronological interactions for prediction.

## 7. Candidate-universe policy
For Phase 1 candidate generation:
1. Candidate items must have a valid canonical ASIN/title.
2. Each session contains exactly 20 candidates: 1 ground-truth next item + 19 negatives.
3. Negative candidates are sampled without replacement from items the user never interacts with anywhere in that user's cleaned full history, including future interactions.
4. Sampling is deterministic under a recorded seed.
5. Candidate order is deterministically shuffled so the ground-truth item is not systematically placed at a fixed position.
6. Candidate sampling logic and seeds are independent of the LLM backend.

This implements the paper's stated use of one ground-truth item plus 19 randomly sampled non-interacted items while adding explicit leakage-prevention and reproducibility rules.

## 8. Output and auditability
The preprocessing pipeline must report at least:
- raw review row count
- rows removed for missing required fields
- rows removed for missing metadata/title
- metadata duplicate ASIN groups collapsed
- exact repeated `(user, item)` groups collapsed
- ambiguous repeated `(user, item)` groups and rows excluded
- final interaction count
- final unique-user count
- final unique-item count
- users eligible for at least one session
- history length summary

Processed datasets, raw datasets, model weights, and large generated artifacts remain local and must not be committed to GitHub.

## Sensitivity analysis reserved for later
After the primary reproduction is stable, we may compare this v1 repeated-pair policy against alternatives such as keeping the earliest or latest repeated review. Such variants must be clearly labeled as secondary experiments and must not silently replace the frozen v1 policy.
