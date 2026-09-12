# Phase 2 Purchased-Item Baseline Comparison

## Scope
This document compares the three purchased-item baselines implemented on the same frozen 20-user / 94-session Video Games pilot:
- Sequential
- Recency-Focused
- In-Context Learning (ICL)

All three runs use the same frozen Phase 1 users, chronology, targets, candidate sets, candidate size, NDCG implementation, active local model, temperature, and generation seed. The baseline-specific difference is prompt framing.

## Frozen local results

| Metric | Sequential | Recency-Focused | ICL |
|---|---:|---:|---:|
| NDCG@1 | 0.061667 | **0.078333** | 0.061667 |
| NDCG@5 | 0.182577 | **0.199726** | 0.186356 |
| NDCG@10 | 0.227799 | 0.239947 | **0.255724** |
| NDCG@20 | 0.366378 | **0.378652** | 0.371370 |
| Total reported tokens | 60,669 | 64,677 | 66,877 |
| Mean latency (s/session) | 1.385 | 1.394 | **1.343** |
| Successful sessions | 94 | 94 | 94 |
| Failed sessions | 0 | 0 | 0 |

## Descriptive observations
- Recency-Focused is the strongest local baseline at NDCG@1, NDCG@5, and NDCG@20.
- ICL is the strongest local baseline at NDCG@10.
- Relative to Sequential, ICL changes NDCG by:
  - NDCG@1: +0.000000
  - NDCG@5: +0.003779 (~+2.07%)
  - NDCG@10: +0.027925 (~+12.26%)
  - NDCG@20: +0.004992 (~+1.36%)
- Recency-Focused used 4,008 more reported tokens than Sequential; ICL used 6,208 more reported tokens than Sequential.
- The measured latency differences are small in this local setup and should not be overinterpreted without repeated controlled runtime measurements.

## Scientific labeling
These are **local derivative-model results** from `llama-3.2-3b-instruct-uncensored`, not exact numerical reproductions of the paper's `Llama-3.2-3B-Instruct` checkpoint results.

The frozen preprocessing and candidate-sampling edge-case policies are also explicit reproduction choices where the paper does not specify implementation details.

## Runtime note
The ICL full run initially reached 93/94 valid sessions while cumulative system-RAM growth was observed in `llama-server.exe`. After restarting the local server without changing the model/generation configuration, resume mode retried only the failed session and the run reached 94/94 PASS. This runtime event is documented and does not replace the final 94-session metric with the earlier incomplete summary.

Before a final thesis-grade efficiency comparison, a single fixed local-server cache/runtime policy should be documented and, if materially changed from these runs, all compared baselines should be rerun under that same policy.
