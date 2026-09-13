# Phase 10B2 v2 — Homogeneous Confirmatory Profile Updater

The first confirmatory Profile Updater attempt stopped after 225 valid states because task `A1WTMP0BQ76WTZ:12` repeatedly returned the same valid ID twice in one category. Fresh retries and the JSON-schema `uniqueItems` hint did not change that local-model behavior. No confirmatory PURE or Recency recommendation outcome has been run or inspected.

For scientific consistency, v2 starts the Profile Updater stage again for all **1,067** updates and does **not** reuse the 225 v1 states. The accepted Phase 4 prompt, v4 retention guard, model, temperature `0.0`, seed `42`, max output tokens `1024`, and `Max Concurrent Predictions = 1` remain unchanged.

The only added normalization is exact duplicate-ID canonicalization. If a category contains the same valid selected ID more than once, later repetitions are reduced to one occurrence before the existing strict parser runs. This preserves the selected set exactly; it does not add, remove, infer, or rewrite any distinct preference evidence.

All other structural problems remain failures: unknown IDs, cross-category IDs, wrong keys, malformed JSON, invalid types, and downstream guard errors. A non-canonicalizable failure may receive at most three fresh requests with the same frozen generation settings.

Frozen design checks remain: 150 new users, 767 sessions, 1,067 update events, cohort SHA256 `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`, and session SHA256 `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`.

v2 writes only to `outputs/phase10_confirmatory_profile_updater_v2/`. Resume is allowed only from rows created under policy marker `exact_duplicate_id_canonicalization_v2`; any mixed-policy state causes an abort.

PASS requires 1,067 valid latest states, zero latest failures, all frozen checks passing, and no use of confirmatory recommendation outcomes in choosing this policy. The final report will disclose the number of responses and ID occurrences affected by canonicalization.
