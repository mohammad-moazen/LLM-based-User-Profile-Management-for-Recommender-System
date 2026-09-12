# Phase 5 PURE Recommender — Full Attempt 1

## Status
**INCOMPLETE — 92/94 sessions succeeded. Do not freeze or report these NDCG values as the final PURE result.**

## Fixed protocol
- frozen Phase 1 sessions: 94
- frozen Phase 4 profile state at `target_position - 1`
- local derivative model: `llama-3.2-3b-instruct-uncensored`
- temperature: 0.0
- seed: 42
- max output tokens: 512
- numbered candidate titles, 20 candidates
- JSON-schema response request plus strict complete-permutation parser
- no semantic repair of malformed rankings

## Result
- requested sessions: 94
- successful sessions: 92
- failed sessions: 2
- users represented among successful sessions: 20
- prompt tokens: 98,825 total, 1,074.185 mean, 2,801 max
- completion tokens: 6,639 total, 72.163 mean
- latency: 196.672 s total, 2.138 s mean

The 92-session aggregate was:
- NDCG@1: 0.104435
- NDCG@5: 0.247248
- NDCG@10: 0.318287
- NDCG@20: 0.416851

These metrics are **provisional diagnostics only** because two sessions are absent and user-level averaging is therefore not the intended complete evaluation.

## Failures
### `A3RQZ1J5F5G104:10`
The model returned 20 integers but duplicated candidate `20` and omitted another candidate. The strict parser rejected the result with `Ranking contains duplicate candidate numbers`.

### `A26C4UAI3IXYF:6`
The model again returned 20 integers but duplicated candidate `20` and omitted another candidate. The strict parser rejected the result with the same error.

## Interpretation
The local serving backend accepted a response that violated the requested `uniqueItems` ranking constraint. Therefore the JSON schema alone cannot be treated as sufficient enforcement for a complete permutation in this environment. The strict parser behaved correctly and prevented malformed rankings from entering evaluation.

No ranking will be repaired by inserting, deleting, or reordering candidates after generation. Before defining the final protocol, the two failures will be tested with a formatting-only corrective retry: the previous invalid response is supplied back to the same model and it is asked to return a complete 1..20 permutation. If that succeeds, the final evaluation will use a single homogeneous policy for all 94 sessions: first attempt under the frozen prompt, followed only on structural/permutation failure by a bounded corrective retry. A clean full rerun will then be required.
