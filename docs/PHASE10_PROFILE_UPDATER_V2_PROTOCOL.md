# Phase 10B2 v2 — Homogeneous Confirmatory Profile Updater

The first confirmatory Profile Updater attempt stopped after 225 valid states because task `A1WTMP0BQ76WTZ:12` repeatedly returned the same valid ID twice in one category. A second v2 run progressed to 839 valid states, then task `A6UW2KEO5UOSA:26` repeatedly returned no parseable JSON on a long prefix. No confirmatory PURE or Recency recommendation outcome has been run or inspected.

For scientific consistency, the final v2 run restarts the Profile Updater stage for all **1,067** updates and does **not** reuse the earlier partial v1/v2 state files. The accepted Phase 4 prompt, v4 retention guard, model, temperature `0.0`, seed `42`, max output tokens `1024`, and `Max Concurrent Predictions = 1` remain unchanged.

Two mechanical safeguards are predeclared for every update in the final v2 run. First, repeated occurrences of the same valid selected ID inside one category are canonicalized to one occurrence before the strict parser runs. This preserves the selected set exactly. Second, if the model output is structurally invalid (for example malformed JSON, no JSON object, unknown ID, cross-category ID, wrong keys, or invalid field type), that generated output is discarded completely. The full concatenated profile is then passed through the already-accepted Phase 4 v4 information-preserving guard as if all evidence were selected.

The structural fallback does not infer preferences and does not use malformed model content. Because the v4 guard receives the full concatenated profile, it preserves unique evidence and can only collapse exact duplicate strings or remove a shorter same-category entry that is strictly dominated by richer overlapping evidence. The cost is potentially less profile compaction, not information loss.

This fallback is therefore treated as an operational robustness rule rather than a semantic repair of model output. It is frozen before any confirmatory recommendation outcome is observed and is applied uniformly to all 1,067 updates in the final v2 rerun.

Frozen design checks remain: 150 new users, 767 sessions, 1,067 update events, cohort SHA256 `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`, and session SHA256 `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`.

The final v2 output directory remains `outputs/phase10_confirmatory_profile_updater_v2/`. Before the final homogeneous rerun, the previous partial v2 directory must be deleted or moved aside so that no earlier state is reused.

PASS requires 1,067 valid latest states, zero unresolved updates, all frozen checks passing, and no use of confirmatory recommendation outcomes in choosing this policy. The final report must disclose the number of responses requiring exact duplicate-ID canonicalization and the number requiring conservative structural fallback.
