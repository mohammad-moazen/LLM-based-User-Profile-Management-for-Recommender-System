# Phase 3 Review Extractor — Pilot v3

## Purpose
Pilot v3 tested a deterministic grounding rule after prompt-only grounding remained insufficient in pilots v1/v2. Every generated likes/dislikes/key-features string had to be a contiguous verbatim span of the source review.

## Result
The first two reviews passed the mechanical span validator. The third review failed on:

`key_features -> breathing LEDs`

The source review explicitly stated that the LEDs can `breathe`, remain solid, or create a wave effect, so the model's phrase was semantically grounded but not verbatim. The runner correctly rejected it under the v3 rule and stopped because `fail_fast = true`.

Observed successful outputs before the failure included review-grounded spans such as:
- Review 1: `It's a wonderful keyboard`, the driver-update complaint, and related review spans;
- Review 2: `I have no complaints with this really`, `more durable than the cheapest mouse and keyboard combo`, `a couple of common gaming features`, and `nice looking keyboard`.

## Interpretation
The v3 validator solved title-only leakage, but the rule was too strict: it conflated **semantic grounding** with **verbatim wording**. A valid interpretation such as `breathing LEDs` can be grounded in an exact review span like `LEDs either breathe` without being an identical string.

Therefore v3 is recorded as:

**Grounding protection successful / representation rule too strict / not accepted for full extraction.**

## Design change for v4
Pilot v4 uses evidence-backed entries:

```json
{
  "value": "breathing LEDs",
  "evidence": "LEDs either breathe"
}
```

The local parser validates only the `evidence` field as an exact review span. The concise `value` may be a faithful paraphrase. For downstream profile construction, the safe extraction uses the verbatim evidence spans; model values are retained for audit only.

This prevents title-only attributes from entering the profile while avoiding false rejection of legitimate paraphrases.
