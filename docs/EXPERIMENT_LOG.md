# Experiment Log

Use this file as a chronological record of meaningful runs and debugging milestones. Do not overwrite past entries; append new entries.

## Entry template

### YYYY-MM-DD — <short experiment name>
- Git commit: `<sha>`
- Phase:
- Dataset/category:
- Data subset:
- Selection seed:
- Candidate seed:
- Model:
- Quantization:
- Context length:
- Temperature:
- Backend/runtime:
- Configuration:
- Number of users:
- Number of recommendation sessions:
- Metrics:
  - NDCG@1:
  - NDCG@5:
  - NDCG@10:
  - NDCG@20:
- Token/context statistics:
- Runtime/performance notes:
- Errors or anomalies:
- Interpretation:
- Next action:

## 2026-09-05 — Dataset schema inspection
- Phase: 0
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Review file: `Video_Games_5.json.gz`
- Metadata file: `meta_Video_Games.json.gz`
- Review file size observed locally: 146.84 MB
- Metadata file size observed locally: 50.81 MB
- First 1000 review records confirmed required fields: `reviewerID`, `asin`, `reviewText`, `overall`, `unixReviewTime`
- First 1000 metadata records confirmed required fields: `asin`, `title`
- Result: schema is suitable for the planned PURE data pipeline
- Next action: run full dataset validator and capture its summary here

## 2026-09-05 — Full Video Games dataset validation
- Phase: 0
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Review file: `Video_Games_5.json.gz`
- Metadata file: `meta_Video_Games.json.gz`
- Total metadata records: 84,819
- Unique metadata ASINs: 71,911
- Duplicate metadata ASIN rows: 12,908
- Metadata rows with empty title: 11
- Metadata missing required fields: 0
- Total review records: 497,577
- Unique users: 55,217
- Unique reviewed items: 17,408
- Review rows missing at least one required field: 158
- Empty review text rows: 0
- Review items missing from metadata lookup: 1,262
- Review-to-metadata title coverage: 99.7464%
- Repeated `(user, item)` rows: 24,149
- Users with at least 3 interactions: 55,211
- Users with at least 4 interactions: 55,210
- Users with at least 5 interactions: 55,200
- User history length: min=1, median=6, mean=9.01, p90=15, p95=20, max=815
- Rating distribution:
  - 1.0: 30,879
  - 2.0: 24,133
  - 3.0: 49,140
  - 4.0: 93,644
  - 5.0: 299,623
- Validation interpretation:
  - Dataset scale and chronological fields are sufficient for the planned sequential recommendation pipeline.
  - Metadata coverage is high enough for the initial implementation, but missing-title interactions must be handled deterministically.
  - Duplicate metadata ASINs and repeated user-item interactions are significant enough that their semantics must be inspected before final preprocessing rules are fixed.
  - A small number of users have fewer than five observed rows despite using the distributed 5-core file; the experiment pipeline will apply an explicit minimum-history eligibility rule rather than relying on the dataset label alone.
- Next action: inspect duplicate metadata records, repeated user-item interactions, missing-required review rows, and metadata misses; then freeze deterministic cleaning rules before producing processed data.

## 2026-09-05 — Dataset anomaly analysis and preprocessing-policy freeze
- Git commit containing anomaly-analysis script: `90194676eb3d15abd89b84cbfb98e88a3e6156c0`
- Phase: 0
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Metadata anomaly results:
  - total metadata rows: 84,819
  - unique ASINs: 71,911
  - duplicate ASINs: 12,908
  - duplicate ASIN groups with more than one distinct non-empty title: 0
  - rows with empty/invalid title: 11
- Review required-field results:
  - total review rows: 497,577
  - rows missing one or more required PURE fields: 158
  - observed examples are missing `reviewText`
- Review-to-metadata miss results:
  - review rows without a usable title: 1,262
  - unique affected ASINs: 19
  - most frequent missing-title ASIN: `B0016C3260` with 418 review rows
- Repeated `(user, item)` results:
  - unique pairs before cleaning: 473,427
  - repeated pairs: 23,937
  - rows beyond the first occurrence: 24,150
  - repeated pairs identical on PURE-relevant fields: 23,361
  - repeated pairs with different timestamp: 389
  - repeated pairs with different review text: 539
  - repeated pairs with different rating: 133
- Interpretation:
  - metadata duplicates are safe to collapse by ASIN because no duplicate group has conflicting non-empty titles
  - missing review text should not be imputed from `summary` in the primary reproduction
  - interactions without a usable metadata title should be removed from the canonical prompt/evaluation dataset
  - repeated user-item rows cannot safely be treated as repeated purchases because the review dataset does not establish purchase-event semantics
  - exact repeated user-item groups will therefore be collapsed; conflicting repeated pairs will be excluded conservatively from preprocessing-policy v1
- Policy status: frozen as `docs/PREPROCESSING_POLICY.md` v1
- Important provenance note: the PURE paper does not document these edge-case cleaning rules; they are explicit decisions in this reproduction and must be reported as such.
- Next action: implement the canonical processed-data pipeline exactly according to preprocessing-policy v1, then report post-cleaning counts before generating recommendation sessions.
