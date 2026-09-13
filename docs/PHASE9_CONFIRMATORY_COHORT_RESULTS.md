# Phase 9 — Confirmatory New-User Cohort Design Results

## Status

**PASS / FROZEN**

Phase 9 completed the prospective confirmatory cohort design without making any LLM calls and without modifying the frozen 20-user pilot results.

## Confirmatory design frozen in Phase 9

- confirmatory cohort: **150 new eligible users**
- original pilot users excluded: **20**
- pilot/cohort overlap: **0**
- eligible users in the cleaned dataset: **54,451**
- deterministic eligible-user ranks selected: **21 through 170**
- user-selection seed: `20260905`
- candidate size: **20**
- candidate seed: `42`
- continuous next-item evaluation after three observed interactions
- full-history exclusion for all negative candidates
- primary comparison: **PURE vs Recency-Focused**
- primary endpoint: **NDCG@10**
- alpha: **0.05, two-sided**
- target power used for planning: **80%**

The original 20 users remain pilot evidence only and are not reused in the confirmatory hypothesis test.

## Frozen workload

- new users: **150**
- recommendation sessions: **767**
- profile evidence events: **1,067**
- cleaned history length: minimum **4**, mean **8.1133**, maximum **35**

For PURE, the 1,067 profile evidence events imply 1,067 Review Extractor calls and 1,067 Profile Updater calls under the existing chronological profile protocol, before the 767 PURE recommendation sessions are evaluated.

## Freeze identifiers

Ordered cohort manifest SHA256:

`72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`

Complete session/candidate manifest SHA256:

`0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

These hashes are the authoritative identity of the Phase 9 confirmatory design. Any later change to user membership, session membership, candidate membership, or candidate order constitutes a new design/version rather than the same confirmatory run.

## Empirical compute estimate

The estimate is derived from empirical rates observed in the accepted 20-user runs. It is a planning estimate, not a runtime guarantee, because the new users have different history lengths and prompt sizes.

### Required primary confirmatory scope

Methods:

- PURE
- Recency-Focused

Estimated workload:

- LLM requests: **~3,676.16**
- reported tokens: **~3,476,714**
- local inference time: **~3.34 hours**

No monetary API cost is assigned because inference is local.

### Optional secondary methods

If Sequential and ICL are also run on the same frozen cohort:

- additional LLM requests: **1,534**
- additional reported tokens: **~1,040,623**
- additional inference time: **~0.52 hours**

Full four-method estimate:

- LLM requests: **~5,210.16**
- reported tokens: **~4,517,337**
- local inference time: **~3.86 hours**

## Scientific interpretation

Phase 9 does not provide new effectiveness evidence. It only freezes the sampling frame and evaluation workload before any confirmatory model output is observed. This separation is intentional: the confirmatory cohort must not be adjusted after inspecting outcomes.

The Phase 10 confirmatory executor must therefore consume the frozen Phase 9 cohort/session manifests directly, verify both SHA256 identifiers before any model call, keep the existing model/prompt/runtime/output-validation protocol unchanged, and report the result whether or not the primary confidence interval excludes zero.

## Authoritative local artifacts

Local output directory:

`outputs/phase9_confirmatory_cohort_v1/`

Key files:

- `cohort_users.json`
- `sessions.jsonl.gz`
- `cohort_summary.json`
- `cost_estimate.json`
- `phase9_report.md`

Protocol: `docs/PHASE9_CONFIRMATORY_COHORT_PROTOCOL.md`.
