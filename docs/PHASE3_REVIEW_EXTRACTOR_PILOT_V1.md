# Phase 3 Review Extractor — Pilot v1 Findings

## Technical result
The first real-data pilot processed the first 3 required historical reviews from the frozen Phase 1 workload.

- required unique extractions in the frozen workload: 134
- requested pilot extractions: 3
- successful extractions: 3
- failed extractions: 0
- users represented: 1
- likes entries: 8
- dislikes entries: 2
- key-feature entries: 10
- total reported tokens: 1,063
- mean latency: 2.109 seconds
- structured-output status: PASS

## Qualitative grounding review
The JSON/schema gate passed, but the semantic grounding gate was not accepted without refinement.

### Review 1
The source review says the keyboard is wonderful and warns that driver updates sometimes break things. The extracted like and dislike were grounded. However, `Cherry MX Red switches` and `RGB LED lighting` appeared under `key_features` even though those attributes were present only in the product title, not discussed in the review text.

### Review 2
The source review explicitly discusses appearance, durability, common gaming features, value, and the absence of major complaints. The extracted likes were grounded. However, `backlit keyboard`, `wired connection`, `gaming mouse`, and `white color` were copied from the product title rather than established as user-relevant features by the review text.

### Review 3
Most extracted content was grounded in the review: Cherry MX Red switches, build quality, backlighting, configurable LED behavior, white-only LEDs, Logitech gaming software, longevity, and PC-gaming use were directly discussed or clearly paraphrased from the review.

## Interpretation
The local derivative model treated title/catalog attributes as eligible `key_features` even when the review itself did not discuss those attributes. This is not an out-of-input hallucination because the title was supplied, but it is too weakly grounded for the intended user-preference representation and can contaminate the evolving profile with attributes the reviewer never expressed as important.

The paper supplies product names alongside reviews but asks the model to analyze likes/dislikes/key features by referring to the reviews. Therefore, for this reproduction, product identity/title and rating remain visible as context, while preference entries and key features must be grounded in the review text itself.

## Decision
Pilot v1 is **technical PASS / semantic refinement required**. It is not used as the accepted extraction set.

The extractor prompt is revised so that:
- ASIN and product title identify the purchased product but are not independent evidence for preferences;
- rating may provide overall sentiment context but cannot create a specific feature/preference by itself;
- title-only attributes must not be copied into `key_features` unless the review text itself mentions or clearly describes them;
- empty arrays are preferred over unsupported extraction.

Pilot v2 reruns the same three reviews into a fresh output directory so the v1 artifacts remain unchanged for auditability.
