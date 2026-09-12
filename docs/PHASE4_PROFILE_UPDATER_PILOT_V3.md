# Phase 4 Profile Updater Pilot v3

## Result
Pilot v3 is a **technical PASS but policy not yet frozen**.

Configuration:
- source: `outputs/phase3_review_extractor_final_1024/extractions.jsonl`
- model: local derivative `llama-3.2-3b-instruct-uncensored`
- users: 2
- chronological updates/user: 4
- expected updates: 8
- temperature: 0.0
- seed: 42
- max output tokens: 1024
- runtime: Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1
- model output: same-category stable entry IDs only
- deterministic post-generation retention guard enabled

Observed summary:
- successful updates: 8/8
- failed updates: 0
- guard-restored entries: 9
- final removed entries across updates: 1
- prompt tokens: 4,706
- completion tokens: 466
- total reported tokens: 5,172
- total latency: 12.895 s
- mean latency: 1.612 s/update

## What v3 fixed
The ID-only output eliminated the v2 string-rewriting failure mode. Every model output referred only to schema-enumerated IDs from the same category, so no paraphrased/new profile text could enter through the updater.

The deterministic guard also restored nine model-omitted entries that lacked a mechanically defensible same-category overlap witness. This prevented the arbitrary unique-evidence deletion observed in pilots v1 and v2.

## Remaining v3 policy defect
The v3 overlap test was symmetric: if two strings clearly overlapped, deletion was allowed regardless of which direction preserved more information. This produced one final deletion in the pilot where the model retained the shorter sentence:

`It has a lot of charm and it is challenging enough.`

and omitted the richer sentence:

`Beautiful game. It has a lot of charm and it is challenging enough.`

The guard treated the omission as valid merely because the two strings overlapped. That direction contradicts the project's own retention rule to preserve the more specific/informative evidence, and risks information loss (`Beautiful game`).

Therefore pilot v3 is not the final frozen updater policy.

## Pilot v4 correction
Pilot v4 keeps the successful ID-only interface, but makes overlap deletion directional:
- an omitted entry may be deleted only when a retained same-category entry strictly dominates it;
- dominance requires clear lexical overlap plus strictly richer normalized/content evidence;
- if the model keeps a shorter overlap and omits a richer one, the richer entry is restored;
- after restoration, a deterministic pass removes the dominated shorter representative;
- unrelated unique omissions remain restored.

Pilot v4 expands coverage to 3 users × 5 chronological updates = 15 updates.

This directional dominance guard is an explicit reproduction engineering safeguard; the PURE paper does not publish an exact updater post-processing algorithm.
