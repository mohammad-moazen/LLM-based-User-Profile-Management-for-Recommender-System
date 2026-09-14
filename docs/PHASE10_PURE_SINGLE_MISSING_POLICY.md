# Phase 10B4 — Blinded handling of one unresolved PURE ranking

Phase 10B4 completed 766 of 767 frozen recommendation sessions. The only unresolved session is `A3C8IUK92R6137:13`. Its direct-ranking path and rank-map fallback both produced structurally invalid permutations. The aggregate confirmatory effectiveness metrics were still withheld when this policy was fixed.

No further model retries will be used for this session. Repeated retries after observing a persistent serialization failure could turn operational recovery into outcome-sensitive selection.

For the pre-declared primary endpoint, PURE vs Recency-Focused on user-level NDCG@10, the unresolved PURE session is assigned NDCG@10 = 0. This is the worst possible NDCG@10 contribution and therefore cannot improve PURE's primary result. The statistical unit remains the user, users remain 150, and the paired two-sided t-test with alpha 0.05 remains unchanged.

Phase 10C will also report two sensitivity views for transparency: (1) observed-only PURE aggregation for the affected user, and (2) an optimistic bound that assigns the unresolved session rank 1. These sensitivity views are secondary and do not replace the conservative primary handling.

No cohort, candidate set, profile state, prompt, model, runtime setting, primary metric, primary comparison, alpha, or statistical unit is changed by this policy.
