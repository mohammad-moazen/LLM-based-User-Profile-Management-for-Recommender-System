# Phase 10B4 — Confirmatory PURE Protocol

Phase 10B4 evaluates PURE on the already frozen Phase 9 confirmatory cohort. The cohort contains 150 new users and exactly 767 recommendation sessions. The cohort and session hashes are unchanged from Phase 9.

Inputs are fixed before this run: Phase 1 canonical items/interactions, Phase 9 frozen sessions and candidate order, and the final PASS Phase 10B2 profile-state artifact. Each recommendation session uses the profile state aligned to `target_position - 1`, so no target or future review evidence is visible before recommendation.

The recommender semantics and output mechanics are inherited from the accepted Phase 5 final hybrid run: chronological purchased-item titles plus the current PURE profile and the 20 frozen candidates; direct complete ranking first; one fresh rank-map request only if the direct output is structurally invalid; strict complete-permutation validation; no deterministic candidate repair and no malformed primary output shown to the fallback.

Generation/runtime are frozen at temperature 0.0, seed 42, max output tokens 512, Context Length 8192, and Max Concurrent Predictions 1. No runtime tuning is allowed after confirmatory effectiveness results exist.

The runner is session-resumable. Successful rows created under `confirmatory_pure_hybrid_v1` are reused only for the same frozen session IDs. Mixed-protocol or non-frozen resume rows cause an abort.

PASS requires 767 successful sessions, zero latest failures, and all 150 users represented. Aggregate NDCG is stored locally for the subsequent Phase 10C paired analysis but intentionally omitted from the Git handoff until both primary methods are complete.

The pre-declared primary analysis remains PURE versus Recency-Focused on user-level mean NDCG@10, using a paired two-sided t-test at alpha 0.05. The confirmatory result will be reported regardless of direction or statistical significance.
