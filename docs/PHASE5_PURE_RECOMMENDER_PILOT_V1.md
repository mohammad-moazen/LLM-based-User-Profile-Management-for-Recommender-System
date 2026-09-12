# Phase 5 PURE Recommender — Pilot v1

## Status
**PASS / accepted for full 94-session evaluation.**

This pilot validates the final PURE recommender plumbing against the frozen Phase 1 sessions and frozen Phase 4 profile-state cache. The reported pilot NDCG values are diagnostic only and are not the final thesis result.

## Frozen inputs
- candidate/session source: frozen Phase 1 artifacts;
- user profile source: `outputs/phase4_profile_updater_final_v4/profile_states.jsonl`;
- target position `t` uses profile state after interaction `t-1`;
- candidate set remains the frozen 20-item set;
- chronological purchase history contains only positions before the target.

## Recommender serialization
The paper defines the recommender as using the updated profile, purchased items, and candidate set. Its published prompt exposes positive aspects, negative aspects, key features, and asks for a ranking of 20 candidates. The exact serialization of the purchased-item history is not published.

Project reproduction choice:
- prepend chronological purchased-item titles;
- serialize the three frozen profile categories exactly;
- show candidate titles with stable prompt-local numbers 1..20;
- hide ASIN identifiers from the model;
- require a strict structured JSON ranking that is a complete unique permutation of 1..20;
- map ranked numbers back to the frozen ASIN list deterministically.

## Generation
- model: `llama-3.2-3b-instruct-uncensored` (local derivative; not exact paper checkpoint);
- temperature: 0.0;
- seed: 42;
- max output tokens: 512;
- structured output: complete numbered-candidate ranking JSON schema;
- finalized LM Studio runtime: 512 / 256 / 1, Context Length 8192.

## Result
- frozen sessions available: 94;
- pilot sessions requested: 6;
- successful sessions: 6;
- failed sessions: 0;
- users represented: 2;
- profile-state alignment: `target_position_minus_one`;
- mean prompt tokens: 651.67;
- maximum prompt tokens: 851;
- mean completion tokens: 72;
- total latency: 11.709 s;
- mean latency: 1.951 s/session;
- status: PASS.

Diagnostic pilot NDCG:
- NDCG@1: 0.000000;
- NDCG@5: 0.000000;
- NDCG@10: 0.119783;
- NDCG@20: 0.274854.

These six-session metrics must not be compared directly with the paper or frozen 94-session baselines.

## Acceptance decision
The pilot is accepted because every requested session completed, each session resolved to the exact preceding frozen profile state, all rankings satisfied the complete-permutation contract, and prompt sizes remained comfortably below the configured context limit.

The next run evaluates all 94 frozen sessions without changing the prompt, profile source, candidate sets, generation parameters, or ranking parser.
