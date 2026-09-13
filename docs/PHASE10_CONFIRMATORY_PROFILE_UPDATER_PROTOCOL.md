# Phase 10B2 — Confirmatory Profile Updater Protocol

## Purpose

Phase 10B2 builds the chronological PURE profile states for the frozen 150-user confirmatory cohort. It consumes only the successful evidence stream produced by Phase 10B1 and reuses the accepted Phase 4 v4 Profile Updater and information-preserving retention guard without changing their prompt, parser, or deletion policy.

## Preflight guards

Before delegating to the updater, the guarded runner verifies:

- Phase 9 cohort SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`;
- Phase 9 sessions/candidates SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`;
- 150 confirmatory users and 767 frozen sessions;
- Phase 10B1 status `PASS`;
- exactly 1,067 required and successful Review Extractor tasks, with zero extractor failures;
- exactly 150 users represented in successful extractor output;
- extractor generation settings `temperature=0`, `max_tokens=1024`, `seed=42`.

Any mismatch aborts the stage.

## Frozen updater behavior

The delegated updater is the same accepted v4 implementation used in the pilot:

1. process each user's validated evidence chronologically;
2. concatenate the previous safe profile with the new validated extraction;
3. ask the model to select same-category entry IDs under the published updater behavior;
4. apply the deterministic information-preserving dominance guard;
5. remove only exact duplicates or same-category overlaps dominated by richer retained evidence;
6. write one safe profile state after every required observed interaction.

Prefix positions must be contiguous for every user. A recommendation target at position `t+1` may later use only the state after position `t`.

## Generation and runtime

- model: local derivative `llama-3.2-3b-instruct-uncensored`
- temperature: 0.0
- max output tokens: 1024
- generation seed: 42
- Context Length: 8192
- Evaluation Batch: 512
- Physical Batch: 256
- Max Concurrent Predictions: **1**

The one-worker schedule is mandatory because the Phase 10A two-worker candidate failed the pre-declared exact-repeatability gate, despite higher throughput.

## Failure policy

`fail_fast=true` is retained from the accepted full Phase 4 runner. The stage is accepted only when all **1,067** updates across all **150** users complete successfully.

Unlike the Review Extractor stage, the accepted Phase 4 full runner does not implement task-level resume. Therefore the Profile Updater should be run while the machine is on stable AC power and should not be intentionally interrupted. If an interruption occurs, preserve the partial local artifact for audit and inspect it before deciding how to restart; do not manually edit profile states.

## Output

Authoritative local directory:

`outputs/phase10_confirmatory_profile_updater_v1/`

Expected files:

- `profile_states.jsonl`
- `summary.json`

The stage is PASS only if:

- users = 150;
- expected updates = 1,067;
- successful updates = 1,067;
- failed updates = 0;
- prefix contiguity invariant = PASS.

## Scientific isolation

Phase 10B2 does not calculate recommendation NDCG and does not change the pre-declared confirmatory endpoint. The primary test remains **PURE vs Recency-Focused at user-level NDCG@10, alpha 0.05 two-sided**. Profile construction is frozen before recommendation-effectiveness results are inspected.
