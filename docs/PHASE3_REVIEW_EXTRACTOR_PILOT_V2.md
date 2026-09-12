# Phase 3 Review Extractor — Pilot v2

## Status
**Technical PASS / semantic grounding still insufficient.**

Pilot v2 reran the same first three frozen historical reviews after strengthening the prompt so ASIN/title were identity context only and rating was sentiment context only.

## Observed qualitative result

### Review 1
The source review praised the keyboard and warned that driver updates sometimes break functionality.

Observed extraction:
- likes: grounded;
- dislikes: grounded;
- key features: grounded in the review, but largely duplicated/rephrased the same driver-update complaint rather than isolating a distinct concrete feature.

### Review 2
The source review discussed appearance, durability, common gaming features, value/price expectations, and no major complaint.

Observed extraction:
- likes such as `durable` and `common gaming features`: grounded;
- dislikes: empty, which is defensible;
- `gaming features`: grounded;
- `backlit keyboard` and `wired mouse`: **not supported by the review text** and appear to have been copied/inferred from the visible product title.

This means prompt-only grounding was insufficient for the active local derivative model.

### Review 3
The extraction was largely well grounded. The review explicitly discussed Cherry MX Red switches, build quality, backlight/LED behavior, Logitech software, white-only LEDs, non-RGB lighting, longevity, and PC gaming.

`mechanical gaming keyboard` was less directly supported than the other entries because the exact phrase was not stated in the review, even though related switch/gaming information was present.

## Decision
Pilot v2 is not accepted as the extraction set for the full 134-review run.

The next version adds **mechanical grounding validation**:

1. Every extracted string must be a short contiguous verbatim span from the review text.
2. The production parser validates each generated entry against the canonical source review after case/whitespace normalization.
3. Title-only, inferred, or paraphrased entries are rejected rather than silently removed or repaired.
4. Product metadata remains visible for paper alignment, but it cannot become accepted profile evidence unless the same text span appears in the review.
5. A fresh output directory is used so prior pilot artifacts remain auditable.

## Pilot v3 output directory

`outputs/phase3_review_extractor_v3/`

## Scientific note
The paper states that the Review Extractor analyzes reviews into likes, dislikes, and key features and reports JSON-schema structured output, but does not publish an exact evidence-validation mechanism. Verbatim-span validation is therefore an explicit reproduction engineering choice introduced to make review grounding deterministic with the active local derivative model.
