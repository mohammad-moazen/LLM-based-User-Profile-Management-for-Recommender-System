# Phase 4 Profile Updater Pilot v2

## Status
**INCOMPLETE / POLICY NOT ACCEPTED**

Pilot v2 retained the exact same-category subset contract from v1, strengthened the prompt to preserve unique evidence by default, and expanded the pilot to two users with four chronological updates each.

## Configuration
- source extractor artifact: `outputs/phase3_review_extractor_final_1024/extractions.jsonl`
- deterministic users: `A174LCVSHN24BT`, `A1DSE0IGSFN2VK`
- intended updates: 8 total (4 per user)
- temperature: 0.0
- seed: 42
- max output tokens: 1024
- runtime: Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1
- validation: exact same-category subset; no new text
- fail fast: enabled

## Technical result
- expected updates: 8
- successful updates before stop: 4
- failed updates: 1
- reported tokens from successful updates: 2,626
- mean successful-update latency: 2.856 s
- status: INCOMPLETE

The first four updates for `A174LCVSHN24BT` parsed successfully. The first update for `A1DSE0IGSFN2VK` failed because the model rewrote a key-feature string instead of copying it exactly. Input evidence was:

`I got this game for Christmas, they bought it from Amazon, NO instructions,`

but the model returned:

`I got this game for Christmas, they bought it from Amazon,`

The strict subset parser correctly rejected the rewritten text.

## Deletion audit
The stronger retention instruction did not eliminate arbitrary deletion.

At update 2 for `A174LCVSHN24BT`, the model removed both:
- `Arrived even faster than i expected.`
- `If you like really challenging games you should get it.`

Neither removal is mechanically supported by duplicate or clear lexical overlap with the retained like `It is so nostalgic and fun and awesome and hard....`.

At update 4, deleting `It has a lot of charm and it is challenging enough.` in favor of the longer retained string `Beautiful game. It has a lot of charm and it is challenging enough.` is defensible as direct overlap. However, the model also removed the unique key-feature evidence `If you like platformers or you have a kid at home you probably want to get this game.`, which had no clear same-category overlap.

## Decision
Pilot v2 is not accepted for the full Profile Updater run. Two independent problems remain:

1. copying long evidence strings in the structured response is brittle and can produce small rewrites that violate the no-new-text contract;
2. prompt-only retention rules do not reliably prevent deletion of unique, non-overlapping evidence.

## Pilot v3 response
Pilot v3 changes the engineering safeguards while keeping the same paper-derived chronological updater role:
- every concatenated entry receives a stable same-category ID;
- the model returns IDs only, eliminating text-copy drift;
- a deterministic retention guard checks every model-requested deletion;
- an omitted unique entry is restored unless a retained same-category entry has clear lexical overlap;
- exact duplicates and obvious overlaps may still be compacted;
- all model selections, guard restorations, and final removals are logged for audit.

This guard is a documented reproduction engineering choice because the paper does not publish its exact schema or deletion-validation algorithm.
