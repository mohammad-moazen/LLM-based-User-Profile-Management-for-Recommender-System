# Phase 4 PURE Profile Updater — Pilot v1

## Purpose
Pilot v1 tested the first implementation of the PURE Profile Updater on the clean frozen Review Extractor artifact. The updater starts from an empty profile and applies chronological updates using only accepted extractor evidence strings.

## Configuration
- model: `llama-3.2-3b-instruct-uncensored`
- source extractor: `outputs/phase3_review_extractor_final_1024/extractions.jsonl`
- users: 1 deterministic eligible user
- updates: first 3 chronological extractions
- temperature: 0.0
- seed: 42
- max output tokens: 1024
- structured output: three arrays (`likes`, `dislikes`, `key_features`)
- validator: every returned string must be an exact member of the same-category concatenated input
- runtime: Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1

## Technical result
- expected updates: 3
- successful updates: 3
- failed updates: 0
- prompt tokens: 1,094
- completion tokens: 330
- total tokens: 1,424
- total latency: 8.521 s
- mean latency: 2.840 s/update
- technical status: PASS

The parser/validator successfully prevented new text, paraphrases, cross-category movement, and duplicate output strings.

## Qualitative finding
Pilot v1 is **not accepted as the final updater policy** despite its technical PASS.

The critical observation occurs at update 2. The concatenated `likes` list contained three unique entries:

1. `Arrived even faster than i expected.`
2. `If you like really challenging games you should get it.`
3. `It is so nostalgic and fun and awesome and hard....`

The updater returned only entries 2 and 3, dropping `Arrived even faster than i expected.`. That removed string was neither a duplicate nor an obvious overlap or direct conflict with the newly added strings. The published PURE updater prompt asks to remove redundant or overlapping information while preserving crucial information; the paper prose additionally describes conflict resolution. It does not establish arbitrary deletion of unique non-conflicting evidence merely to shorten the profile.

Therefore pilot v1 exposed an over-compression risk: the prompt allowed the model too much discretion to discard unique evidence.

At update 3, the updater also removed one key-feature string (`the swap machines`) while retaining a longer related sentence in `dislikes`. This may be defensible as overlap/conflict handling, but it reinforces the need to audit exactly which strings are removed at every update rather than judging only profile-size reduction.

## Decision
**Pilot v1: TECHNICAL PASS / SCIENTIFIC POLICY NOT ACCEPTED.**

The subset-preserving validator remains valuable and is retained. Pilot v2 will tighten only the deletion policy:

- remove entries only for clear duplicate/redundancy/overlap or clear conflict;
- preserve unique non-overlapping, non-conflicting evidence even if it seems less relevant;
- do not delete an entry merely to make the profile shorter;
- when conflict is uncertain, preserve rather than silently discard;
- continue forbidding new text, paraphrase, cross-category movement, and outside knowledge;
- explicitly report removed strings in the handoff for qualitative audit.

Pilot v2 will also broaden coverage beyond one user while keeping the same final Review Extractor source and finalized runtime.
