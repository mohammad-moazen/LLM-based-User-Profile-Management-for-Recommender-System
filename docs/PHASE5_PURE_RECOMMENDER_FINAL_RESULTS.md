# Phase 5 PURE Recommender — Final Hybrid v4 Results

## Status

**PASS / FROZEN**

This is the authoritative final PURE recommender result for the current local reproduction protocol. Earlier direct-ranking, retry, scored-output, rank-map, and hybrid-pilot runs remain diagnostic/historical records and must not be substituted for this result.

## Scope and scientific label

- Dataset/workload: the 94 frozen Phase 1 continuous recommendation sessions over 20 selected users.
- Candidate set: exactly 20 frozen candidates per session.
- Model: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB).
- This is a **local derivative-model reproduction result**, not an exact reproduction of the paper checkpoint.
- Target position `t` uses only purchases and the frozen PURE profile state through `t-1`.
- NDCG is first averaged over sessions within each user, then averaged across users.

## Frozen output policy

Every session uses one uniform predefined policy:

1. Request the direct numbered candidate ranking first.
2. Validate the model output with the strict complete-permutation parser.
3. Only if that direct model output is structurally invalid, discard it and issue one fresh rank-map request from the same frozen history, profile, candidate set, model, temperature, seed, and token cap.
4. Do not show the malformed direct response to the fallback call.
5. Allow at most one rank-map fallback request per session.
6. Accept the fallback only if its strict parser validates a complete permutation.
7. Do not insert, delete, infer, reorder, rescore, or otherwise repair candidates after generation.
8. API failures or unrelated validation failures do not silently trigger the serialization fallback.

The paper specifies the recommendation/ranking task but does not publish an exact machine-readable output schema. The hybrid serialization is therefore an explicit reproduction engineering choice.

## Generation/runtime

- temperature: `0.0`
- seed: `42`
- max output tokens: `512`
- Context Length: `8192`
- Evaluation Batch: `512`
- Physical Batch: `256`
- Max Concurrent Predictions: `1`

Temperature 0 plus a fixed seed is treated as a recorded generation setting, not as a guarantee of bit-for-bit identical outputs across separate LM Studio executions.

## Final run result

| Measure | Result |
|---|---:|
| Frozen sessions | 94 |
| Requested sessions | 94 |
| Successful sessions | 94 |
| Failed sessions | 0 |
| Users | 20 |
| Direct-primary successes | 93 |
| Fallback attempts | 1 |
| Fallback successes | 1 |
| Total LLM requests | 95 |
| Status | **PASS / FROZEN** |

The only fallback-triggered session was `A26C4UAI3IXYF:6`. Its direct response failed with `Ranking contains duplicate candidate numbers`; the fresh rank-map fallback passed and placed the target at rank 9.

## Final NDCG

| Metric | Final local result |
|---|---:|
| NDCG@1 | **0.1042507003** |
| NDCG@5 | **0.2435534924** |
| NDCG@10 | **0.3183764185** |
| NDCG@20 | **0.4160225252** |

These are the final PURE metrics to use in the later thesis comparison table for this reproduction configuration.

## Token usage

| Measure | Result |
|---|---:|
| Prompt tokens | 101,887 |
| Completion tokens | 6,938 |
| Total reported tokens | 108,825 |
| Mean prompt tokens/request | 1,072.4947 |
| Max prompt tokens/request | 2,801 |
| Mean completion tokens/request | 73.0316 |

## Latency

| Measure | Result |
|---|---:|
| Total request latency | 205.9349 s |
| Mean request latency | 2.1677 s |
| Mean session latency | 2.1910 s |
| Median session latency | 2.0284 s |

## Authoritative artifacts

- Local output directory: `outputs/phase5_pure_recommender_hybrid_final_v4/`
- Session-level results: `outputs/phase5_pure_recommender_hybrid_final_v4/results.jsonl`
- Summary: `outputs/phase5_pure_recommender_hybrid_final_v4/summary.json`
- Runner: `scripts/run_phase5_pure_recommender_hybrid_full.py`
- Safe runner: `scripts/run_phase5_pure_recommender_hybrid_full_safe.py`
- Config: `config/phase5_pure_recommender_hybrid_full.toml`

## Interpretation boundary

The final PURE result is internally complete for the frozen 20-user/94-session workload and accepted output policy. It should not be compared as a fully controlled final table against the historical Phase 2 baseline artifacts, because those historical baseline runs predate the finalized Phase 5 output protocol. Sequential, Recency-Focused, and ICL must be rerun under the same finalized runtime/generation/output policy before the final thesis comparison is frozen.
