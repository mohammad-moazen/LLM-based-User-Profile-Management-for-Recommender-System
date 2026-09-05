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
