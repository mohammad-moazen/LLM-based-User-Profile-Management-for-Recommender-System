# Phase 3 Review Extractor — Pilot v4 Result

## Status
**ERROR / refinement required.**

Pilot v4 introduced an evidence-backed JSON schema in which every extracted item contains:

- `value`: a concise model interpretation;
- `evidence`: a claimed contiguous quote from the source review.

The downstream-safe representation uses only validated evidence spans.

## Frozen pilot basis
- active model: `llama-3.2-3b-instruct-uncensored`
- local derivative-model result; not exact paper-checkpoint reproduction
- same first 3 canonical reviews used in pilots v1-v3
- temperature: 0.0
- max output tokens: 512
- seed: 42
- stable LM Studio runtime profile
- fail-fast: enabled

## Observed result
### Review 1 — accepted
The extractor produced review-grounded entries:

- like evidence: `It's a wonderful keyboard,`
- dislike evidence: `be cautious with driver updates which seem to break certain things with the keyboard occasionally :/`
- no accepted key features

The normalized model values were retained only for audit; the profile-safe extraction stored the verbatim evidence spans.

### Review 2 — rejected by grounding validator
The model produced several valid review-grounded entries, including:

- `a nice looking keyboard`
- `more durable than the cheapest mouse and keyboard combo you can find`
- `has a couple of common gaming features`

However, it also generated this key-feature pair:

```json
{
  "value": "backlit",
  "evidence": "rainbow backlit wired gaming keyboard mouse combo"
}
```

The claimed evidence is not present in the review text; it is derived from the product title. The deterministic evidence validator correctly rejected the response with:

`Review Extractor produced non-verbatim review evidence; field='key_features', value='backlit', evidence='rainbow backlit wired gaming keyboard mouse combo'`

### Review 3 — not run
Because pilot v4 used `fail_fast = true`, execution stopped at Review 2 and Review 3 was not processed.

## Interpretation
Pilot v4 confirms two things:

1. Separating model interpretation from explicit evidence is useful because legitimate paraphrases can be retained for audit while profile input remains anchored to review text.
2. Prompt instructions plus an evidence field are still insufficient to guarantee that the active local derivative model will always quote the review rather than product metadata.

The validator behaved correctly; the remaining weakness is that one unsupported generated entry caused the entire otherwise-useful extraction response to fail.

## Decision for pilot v5
Pilot v5 keeps the evidence-backed schema but changes grounding validation from whole-response rejection to **entry-level conservative filtering**:

- structurally malformed responses still fail;
- each generated evidence entry is checked independently against the source review;
- grounded entries are retained;
- unsupported entries are rejected and logged with field/value/evidence/reason;
- rejected entries are never rewritten, inferred, or replaced;
- only accepted review-grounded evidence can enter the downstream profile.

This is an explicit reproduction engineering choice for the active local derivative model. The PURE paper reports structured JSON output but does not publish this exact grounding/filtering mechanism.

## Audit source
The v4 outcome was received through the tracked experiment mailbox `handoff/latest.json`, then summarized here before the mailbox was reset for the next run.
