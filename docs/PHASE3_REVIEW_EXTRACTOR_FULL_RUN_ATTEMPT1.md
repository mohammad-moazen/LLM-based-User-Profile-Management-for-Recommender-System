# Phase 3 Review Extractor — Full Run Attempt 1

## Status
**INCOMPLETE — 131/134 successful; 3 retryable failures**

This run used the accepted pilot-v5 evidence-backed Review Extractor policy on all 134 unique historical reviews required by the 94 frozen recommendation sessions.

## Runtime / model basis
- model: `llama-3.2-3b-instruct-uncensored`
- result label: local derivative-model result; not exact paper-checkpoint reproduction
- temperature: 0.0
- generation seed: 42
- max output tokens: 512
- structured output: evidence-backed JSON Schema
- grounding policy: entry-level verbatim-evidence filtering
- finalized LM Studio runtime profile unchanged

## Result
- required unique extractions: 134
- requested: 134
- successful: 131
- failed: 3
- users represented by successful extractions: 20
- accepted likes entries: 224
- accepted dislikes entries: 95
- accepted key-feature entries: 156
- unsupported generated entries rejected safely: 34
- total reported tokens: 90,055
- mean successful-request latency: 3.848 seconds
- total successful-request latency: 504.068 seconds (~8.40 minutes)
- status: INCOMPLETE

The 34 rejected unsupported entries did not enter the downstream-safe profile representation. Their presence is expected under the accepted conservative-filtering policy and is not counted as a failed extraction.

## Three failed tasks
The only three failures were:

- `A3RQZ1J5F5G104:2`
- `A2BFIYZYNK54QX:17`
- `A30QZOB8GIOBJO:1`

All three failed for the same reason: the model emitted one or more evidence objects with an empty string in `evidence`, specifically inside `key_features`. Valid entries in those responses were otherwise present.

Examples included model values such as:
- `durable construction` with `evidence: ""`
- `wireless connectivity` with `evidence: ""`
- `WWII setting` with `evidence: ""`

The previous parser treated blank evidence as a response-level validation error before the entry-level conservative filter could run.

## Retry patch
The parser policy is refined as follows:

1. non-string evidence remains a structural error;
2. blank-string evidence is treated as an unsupported semantic entry;
3. that individual entry is rejected with reason `empty_evidence`;
4. other valid entries from the same response are preserved;
5. the JSON schema and prompt now additionally discourage empty evidence (`minLength = 1` plus an explicit instruction to omit unsupported entries).

No blank evidence can enter the profile-safe representation.

This refinement is consistent with the already accepted v5 principle: invalid evidence is rejected entry-by-entry rather than causing unrelated grounded entries to be discarded.

## Resume strategy
The output directory remains the accepted v5 directory and `resume = true` remains enabled. Therefore the next run should skip the 131 successful tasks and retry only these 3 failed tasks.

Once all 134 tasks are successful, the Review Extractor stage can be frozen and the project can proceed to Profile Updater.

## Performance note
The run confirmed that the current sequential local inference path averages about 3.85 seconds per successful extraction. This is scientifically usable but leaves room for throughput optimization. Performance tuning will be benchmarked separately after the extractor result is complete so the accepted scientific run is not mixed with changing runtime settings.
