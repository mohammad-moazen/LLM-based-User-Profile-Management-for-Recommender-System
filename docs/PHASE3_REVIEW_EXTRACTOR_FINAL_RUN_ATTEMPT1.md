# Phase 3 Review Extractor — clean final run attempt 1

## Purpose
This run was the first clean attempt to generate all 134 required historical review extractions from scratch under one final Review Extractor prompt/schema/parser and the finalized LM Studio runtime profile (`Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1`). It writes to `outputs/phase3_review_extractor_final/` and does not overwrite the earlier v5 development artifact.

## Result
- required/requested extractions: 134
- successful extractions: 133
- failed extractions: 1
- users represented by successful rows: 20
- accepted likes entries: 233
- accepted dislikes entries: 93
- accepted key-feature entries: 149
- rejected unsupported/blank-evidence entries: 48
- prompt tokens reported for successful rows: 73,658
- completion tokens reported for successful rows: 21,942
- total reported tokens for successful rows: 95,600
- total successful-request latency: 513.118 seconds
- mean successful-request latency: 3.858 seconds
- status: INCOMPLETE

## Single failed task
Task: `A2BFIYZYNK54QX:12`

The local model returned a structured-output response that the strict JSON parser could not decode:

`Review Extractor response contains invalid JSON: Expecting ',' delimiter: line 40 column 6 (char 2020)`

The failure is a response-serialization/structured-output failure; it is not a grounding-filter rejection and it does not indicate a dataset or RAM failure. The current handoff did not preserve the model server's `finish_reason` for this failed response, so the exact cause (for example an output-cap termination versus another structured serialization issue) is not yet proven.

## Diagnostic before changing protocol
Do **not** change the final experiment configuration yet. A read-only single-task diagnostic was added:

```powershell
python scripts/diagnose_phase3_failed_task.py
```

It replays only `A2BFIYZYNK54QX:12` with the same final prompt/schema/parser, temperature `0.0`, seed `42`, and model, but with a diagnostic completion cap of 1024 tokens. It does not modify `outputs/phase3_review_extractor_final/`.

The diagnostic records:
- server `finish_reason`;
- token usage;
- latency;
- parser PASS/FAIL;
- raw structured response;
- validated extraction if parsing succeeds.

Only after this diagnostic should the final recovery policy be chosen. This avoids silently changing the scientific protocol based on an unverified assumption.
