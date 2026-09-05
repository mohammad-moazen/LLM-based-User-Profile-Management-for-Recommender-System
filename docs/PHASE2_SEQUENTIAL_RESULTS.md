# Phase 2 Sequential Baseline — Frozen Result

## Status
**PASS / FROZEN** for the current 20-user Video Games pilot using the active local derivative model.

## Model and protocol label
- Active model: `llama-3.2-3b-instruct-uncensored`
- Model label: local derivative-model result; not exact reproduction of the paper's `Llama-3.2-3B-Instruct` checkpoint
- Dataset: Amazon Review Data 2018 / Video Games 5-core
- Frozen users: 20
- Frozen continuous sessions: 94
- Candidate size: 20
- Candidate generation: frozen Phase 1 candidate sets
- Temperature: 0.0
- Max output tokens: 512
- Generation seed: 42
- Aggregation: mean across sessions within each user, then mean across users

## Final full-run result
- successful sessions: 94
- failed sessions: 0
- users: 20
- NDCG@1: 0.061667
- NDCG@5: 0.182577
- NDCG@10: 0.227799
- NDCG@20: 0.366378
- total tokens reported by local server: 60,669
- mean latency per session: 1.385 seconds
- run status: PASS

## Validation history
The first two real-model pilot attempts were rejected before metrics because of output-formatting failures:
1. an incomplete 3-entry ranking caused by an ellipsis-style pseudo-JSON instruction;
2. a 23-entry ranking that copied the 3 history ASINs plus all 20 candidate ASINs.

The final validated protocol uses:
- purchase-history titles only;
- numbered candidate titles only;
- no ASINs shown to the model;
- complete permutation of candidate numbers 1..20 as JSON output;
- deterministic mapping from ranked candidate numbers back to the unchanged frozen ASIN list.

This output-interface adaptation changes serialization only. It does not change the frozen users, histories, targets, candidate sets, or NDCG computation.

## Freeze decision
The Sequential baseline is frozen for the current derivative-model experiment because:
- all 94 sessions completed successfully;
- all outputs passed complete-permutation validation;
- no session was omitted from metrics;
- user-first NDCG aggregation completed successfully;
- token and latency totals were captured.

The next purchased-item baseline is Recency-Focused.
