# Phase 10B4 — PURE operational continuation after structural output failure

## Trigger

The first confirmatory PURE invocation completed 642 of 767 frozen sessions and stopped on session `A3C8IUK92R6137:13` because the strict rank-map fallback parser rejected a non-permutation output (`duplicates=[20], missing=[13]`). No confirmatory effectiveness metric was inspected; the Git handoff remained blinded.

## Operational amendment

The execution control `fail_fast` is changed from `true` to `false` for the remaining confirmatory PURE workload. This amendment changes only whether the runner stops after a structural failure. It does **not** change any recommendation prompt, candidate set, profile state, model/runtime setting, generation setting, ranking parser, fallback trigger, fallback format, scoring rule, or NDCG computation.

Existing successful sessions remain resumable and are not rerun. Any structurally invalid session remains recorded as an error and is not repaired, imputed, dropped from the frozen design, or converted into a ranking by this continuation step. The purpose is only to finish traversing the full 767-session frozen cohort so that the total number and type of unresolved serialization failures can be known before any separate recovery decision is made.

## Frozen controls retained

- Phase 9 cohort and session hashes unchanged.
- 150 confirmatory users and 767 sessions unchanged.
- temperature = 0.0.
- seed = 42.
- max output tokens = 512.
- Context Length = 8192.
- Max Concurrent Predictions = 1.
- accepted direct-ranking plus one fresh rank-map structural fallback remains unchanged.
- no post-generation ranking repair.
- aggregate effectiveness metrics remain withheld until the primary-method runs are operationally complete.

This document records an execution-control amendment, not an effectiveness-driven method change.
