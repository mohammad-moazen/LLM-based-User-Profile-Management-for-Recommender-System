# Phase 10B2 — Context-overflow conservative fallback protocol

Phase 10B2 v2 reached 841 valid profile states before task `A6UW2KEO5UOSA:28` exceeded the frozen local context window: the server reported 8,277 prompt tokens against an 8,192-token context. No confirmatory PURE/Recency recommendation outcome has been run or inspected.

The frozen runtime is intentionally kept unchanged: context length 8,192, Max Concurrent Predictions 1, temperature 0.0, seed 42, max output tokens 1,024. We do not increase context mid-cohort because that would mix runtime conditions.

The primary Profile Updater path remains unchanged. Exact duplicate selected IDs are mechanically canonicalized as already defined by v2, then the strict parser and information-preserving guard v4 are applied.

A new conditional fallback is added only when the primary updater cannot yield a usable state. For a deterministic context-overflow error, or after three unusable primary attempts for another structural failure, the failed model output is discarded. The fallback treats the exact concatenation of the previous safe profile and the new extraction as selected, then applies only the already accepted retention guard v4.

This fallback does not infer or delete unique preference evidence from a failed response. Its only expected cost is weaker profile compaction; exact duplicates and strictly dominated same-category overlaps may still be removed by guard v4. Therefore the fallback is conservative with respect to information retention.

Previously successful v2 states are reused. This does not create a mixed semantic policy because the primary branch is unchanged and the new rule is conditional: those successful states would take the same primary branch under the updated protocol. Only tasks for which the primary branch is unavailable use the fallback.

Every fallback state is explicitly marked in the audit artifact with `fallback_used=true`, `fallback_policy="preserve_all_then_guard_v4"`, and a reason. The final Phase 10B2 report must disclose the number and reasons for fallback states.

PASS still requires exactly 1,067 successful latest profile states, zero latest failures, the frozen Phase 9 cohort/session hashes, and no use of confirmatory recommendation outcomes in choosing this policy.
