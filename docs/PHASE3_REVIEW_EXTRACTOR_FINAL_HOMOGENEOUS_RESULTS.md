# Phase 3 PURE Review Extractor — Final Homogeneous Result

## Status
**PASS / FROZEN**

This is the thesis-grade Review Extractor artifact. Unlike the historical development directory, every required extraction in this artifact was generated from scratch under one unchanged final prompt/schema/parser, one generation configuration, and one finalized LM Studio runtime profile.

## Experimental basis
- Dataset: Amazon Review Data 2018 / Video Games 5-core
- frozen users: 20
- frozen continuous recommendation sessions: 94
- required unique historical review extractions: 134
- active local model: `llama-3.2-3b-instruct-uncensored`
- model label: local derivative model; not exact paper checkpoint reproduction
- temperature: 0.0
- generation seed: 42
- max output tokens: 1024
- structured output: evidence-backed JSON schema
- grounding validator: entry-level verbatim evidence filter
- LM Studio runtime: Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1
- output directory: `outputs/phase3_review_extractor_final_1024/`

## Final result
- requested extractions: 134
- successful extractions: 134
- failed extractions: 0
- users represented: 20
- accepted likes entries: 240
- accepted dislikes entries: 98
- accepted key-feature entries: 152
- total accepted entries: 490
- rejected unsupported/blank-evidence entries: 45
- total generated entries before grounding filter: 535
- entry rejection rate: 8.41%
- prompt tokens: 74,956
- completion tokens: 22,394
- total reported tokens: 97,350
- total successful-request latency: 724.650 seconds (~12.08 minutes)
- mean latency: 5.408 seconds/extraction
- status: PASS

## Interpretation
The 45 rejected entries are expected conservative-filter events, not failed tasks. They do not enter the downstream profile-safe representation. Only mechanically validated review-grounded evidence from each successful `extraction` field is eligible as Profile Updater input.

The higher 1024-token ceiling was adopted after the clean 512-token run failed on one long structured-output case. A focused diagnostic on that task completed successfully with `finish_reason=stop` and 495 completion tokens when the ceiling was raised to 1024. The final artifact therefore reran all 134 tasks from scratch at the 1024 ceiling rather than mixing rows generated under different ceilings.

## Frozen downstream contract
Profile Updater must consume only successful rows from:

`outputs/phase3_review_extractor_final_1024/extractions.jsonl`

For each interaction, downstream-safe input is the row's `extraction` object containing only:
- `likes`
- `dislikes`
- `key_features`

`extraction_details.value`, raw model responses, rejected entries, product titles, ratings, and future/target reviews are audit/context fields and must not be substituted for profile-safe evidence.

## Reproducibility notes
The paper reports Llama-3.2-3B-Instruct and JSON-schema structured output, but does not publish its exact machine-readable extractor schema or grounding validator. The evidence-backed schema and conservative evidence filtering are explicit reproduction engineering choices for this project.

The final artifact is homogeneous with respect to the active local model identifier, final extractor prompt/schema/parser, temperature, seed, max-token ceiling, and finalized loader profile. It should be preserved and not overwritten by later experiments.
