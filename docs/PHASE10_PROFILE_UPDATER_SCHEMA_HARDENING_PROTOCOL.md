# Phase 10B2 — Schema-hardening recovery protocol

The first confirmatory Profile Updater run stopped after 225 accepted states because task `A1WTMP0BQ76WTZ:12` returned duplicate ID `D011`. Three fresh retries under the original schema reproduced the same structural violation. No confirmatory recommendation outcome had been inspected at that point.

The prompt and parser already prohibited duplicate IDs. Recovery v2 therefore changes only constrained-decoding enforcement: each updater ID array is given JSON Schema `uniqueItems: true`. The semantic output contract is unchanged. Previously accepted states are reused because they already passed the strict duplicate-rejecting parser.

No response is edited, deduplicated, repaired, or semantically rewritten. Missing or invalid tasks receive fresh requests with the same local model, prompt, temperature 0.0, seed 42, max_tokens 1024, one-worker runtime, and the same retention guard. At most three schema-hardened fresh attempts are allowed per unresolved task. If a task still fails, the run remains incomplete and stops.

This operational amendment was frozen before PURE or Recency confirmatory recommendation outcomes were generated or inspected.
