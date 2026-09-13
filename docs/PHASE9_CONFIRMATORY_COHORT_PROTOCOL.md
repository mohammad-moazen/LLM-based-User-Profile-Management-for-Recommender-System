# Phase 9 — Confirmatory New-User Cohort Design Protocol

## Purpose
Phase 9 freezes a future confirmatory cohort before any new model output is observed. It makes zero LLM calls and does not alter Phases 5–8.

## Confirmatory design
Phase 8 fixed the primary comparison as **PURE vs Recency-Focused on NDCG@10**, with alpha 0.05 two-sided and 80% target power. Its practical planning target is **150 new users**. The original 20 users remain pilot evidence and are excluded from the confirmatory hypothesis test.

## Deterministic user selection
Phase 9 reuses the Phase 1 rule:

- minimum observed history before the first target: 3 interactions;
- eligible history length: at least 4;
- user-selection seed: `20260905`;
- deterministic ordering: SHA256-derived key of `(selection_seed, user_id)`, then `user_id`.

The script first verifies that the original 20 pilot users equal the first 20 eligible users under this ordering. It then selects the next 150 eligible users after excluding the pilot. No model output, review content, rating, profile, or recommendation score is used for selection.

## Frozen sessions and candidates
For each new user with cleaned history length `L`, all continuous next-item sessions are generated from target positions 4 through `L`, so the user contributes `L - 3` sessions.

Each session has exactly 20 candidates: one ground-truth target plus 19 negatives. Negatives are sampled only from items the user never interacts with anywhere in the cleaned full history. Candidate seed is `42`, using the same Phase 1 SHA256-derived per-session seed and deterministic shuffle.

The script validates user membership, target alignment, candidate count, uniqueness, target inclusion, and full-history negative exclusion.

## PURE profile workload
For a user with history length `L`, evaluation through the final target requires profile evidence through the penultimate interaction, so Review Extractor and Profile Updater each require `L - 1` events. Phase 9 only counts these events; it does not run them.

## Execution scope
The required confirmatory scope is only:

1. PURE;
2. Recency-Focused.

Sequential and ICL are optional secondary methods. This keeps the confirmatory claim aligned with the Phase 8 pre-declared comparison and avoids unnecessary multiplicity and compute.

## Compute planning
Phase 9 estimates future request count, reported tokens, and inference time from empirical rates observed in the accepted 20-user runs. These are planning estimates, not guarantees, because new-user histories can change prompt lengths. No API monetary cost is assigned because inference is local.

## Freeze identifiers
The output records SHA256 hashes for the ordered cohort manifest and complete session manifest. Any later change to users, sessions, or candidates changes these hashes and is a new design/version.

## Anti-p-hacking rules
Before any Phase 10 model call, the following remain fixed: 150 new users, exclusion of the original 20, selection/candidate seeds, all sessions and candidate order, PURE vs Recency-Focused, NDCG@10, alpha 0.05 two-sided, equal-user aggregation, and the existing model/prompt/output-validation/runtime protocol. The result must be reported whether significant or not.

## Outputs
Local output directory:

`outputs/phase9_confirmatory_cohort_v1/`

Expected files:

- `cohort_users.json`
- `sessions.jsonl.gz`
- `cohort_summary.json`
- `cost_estimate.json`
- `phase9_report.md`

## Acceptance criteria
PASS requires exactly 150 new users, zero pilot overlap, valid deterministic sessions/candidates for every user, written cohort/session hashes, and zero LLM calls.
