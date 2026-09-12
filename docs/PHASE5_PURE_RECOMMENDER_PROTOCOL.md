# Phase 5 PURE Recommender Protocol

## Purpose
Phase 5 reproduces **STEP 3: Recommend Next Purchase Item** from PURE using the frozen Phase 1 recommendation sessions and the frozen Phase 4 profile-state cache.

## Paper-derived behavior
Algorithm 1 defines the prediction as:

`pred = R(P_t, I_t, C_(t+1))`

Therefore the recommender uses the current updated user profile, the purchased-item history, and the candidate set. The paper prose likewise states that the Recommender reranks candidates by leveraging the updated profile and purchased items.

The published prompt template is:

> Positive aspects: {likes} Negative aspects: {dislikes} Key Features: {key features} Based on these inputs, rank the {candidate list} from 1 to 20 by evaluating their likelihood of being purchased.

The paper does not show exactly how the purchased-item history is serialized inside this prompt. This reproduction explicitly prepends the chronological purchased-item titles, then supplies the published profile labels and numbered candidate list. This is a documented reproduction serialization choice made to remain consistent with Algorithm 1 and the paper's component description.

## Leakage-safe session mapping
For a frozen session whose target is purchase position `t`:
- observed purchase history = positions `1..t-1`;
- eligible profile state = frozen Phase 4 state after interaction position `t-1`;
- target review and all future reviews are unavailable;
- the frozen 20-item candidate set is unchanged.

A missing or mismatched `(user_id, t-1)` profile state is a hard error.

## Candidate interface
The stable numbered-candidate interface from Phase 2 is retained:
- purchase history is represented by canonical product titles;
- each candidate title is assigned prompt-local number `1..20`;
- ASINs are hidden from the LLM because they add no semantic recommendation information and previously caused local-model copying errors;
- the parser deterministically maps candidate numbers back to the frozen ASIN order.

The candidate set and target are never changed or semantically repaired.

## Structured output
The paper states that JSON schemas were used to improve output consistency. Phase 5 therefore requests a strict schema:

```json
{
  "ranking": [1, 2, 3, "...", 20]
}
```

The array must contain all 20 candidate numbers exactly once. The existing strict Phase 2 ranking parser then verifies a complete permutation and maps it back to ASINs.

## Evaluation
For every successful session:
1. obtain the target rank;
2. compute NDCG@1, @5, @10, and @20;
3. aggregate sessions within each user;
4. average user-level scores equally across users.

This matches the frozen evaluation policy used by the project and the paper's continuous sequential recommendation description.

## Pilot v1
The initial pilot validates the full Phase 4 → Phase 5 handoff before a 94-session run.

Configuration:
- first 6 frozen sessions;
- final frozen Phase 4 state artifact: `outputs/phase4_profile_updater_final_v4/profile_states.jsonl`;
- temperature: 0.0;
- seed: 42;
- max output tokens: 512;
- structured complete-ranking JSON schema;
- finalized local runtime: Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1;
- output: `outputs/phase5_pure_recommender_pilot/`.

Acceptance requires:
- 6/6 sessions successful;
- exact target-position-minus-one profile alignment for every session;
- 20-item complete ranking for every session;
- no malformed structured outputs;
- prompt sizes comfortably below the 8,192-token context setting.

Pilot NDCG is diagnostic only because the six sessions are not a full user-balanced evaluation. Final reported PURE metrics require the full 94-session run.

## Scientific labeling
The active model is the local derivative `llama-3.2-3b-instruct-uncensored`, not the exact `Llama-3.2-3B-Instruct` checkpoint used in the paper. Final metrics must therefore be described as local derivative-model reproduction results rather than exact paper-score reproduction.
