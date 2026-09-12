# Phase 5 PURE Recommender — Scored-output Pilot v2

## Status
**Technical PASS / final-policy NOT accepted.**

The pilot tested a score-based machine-readable serialization after direct ranking arrays failed structurally in 2 of 94 sessions and a deterministic corrective retry failed 0/2.

## Fixed experimental inputs
The following were unchanged from the accepted PURE recommender protocol:
- frozen Phase 1 sessions and 20-item candidate sets;
- frozen Phase 4 profile states;
- target-position-minus-one profile alignment;
- chronological purchased-item titles and profile serialization;
- local derivative model `llama-3.2-3b-instruct-uncensored`;
- temperature 0.0, seed 42, max output tokens 512;
- finalized LM Studio runtime.

Only output serialization changed. The model emitted one integer purchase-likelihood score in `[0,1000]` for every candidate key. Ranking was derived by descending score with frozen candidate number ascending as a deterministic tie-break.

## Coverage
The pilot included the original six successful Phase 5 pilot sessions plus both known direct-ranking failure sessions:
- `A3RQZ1J5F5G104:10`
- `A26C4UAI3IXYF:6`

## Result
- requested/successful/failed: **8 / 8 / 0**
- users represented: 4
- both known direct-ranking failures succeeded under the score schema: **2 / 2**
- prompt tokens: 7,071 total; 883.875 mean; 1,658 max
- completion tokens: 1,253 total; 156.625 mean
- latency: 30.788 s total; 3.849 s mean
- diagnostic NDCG@1/5/10/20: 0.000000 / 0.265402 / 0.265402 / 0.390355

## Tie audit and rejection rationale
Every one of the 8 sessions contained score ties:
- sessions with ties: **8 / 8**
- total tie groups: **12**
- total candidates participating in tied groups: **152**

Several sessions assigned the same score to 19 or all 20 candidates. Therefore a substantial fraction of the final ordering was determined by the deterministic candidate-number tie-break rather than by model preference. Although the frozen candidate order is target-independent and was already randomized in Phase 1, this behavior is too degenerate to use as the thesis-grade final ranking protocol.

The score-based protocol is therefore retained as a useful structural diagnostic but **is not accepted for the final 94-session PURE evaluation**.

## Next protocol
Pilot v3 uses a candidate-to-rank map instead of either a ranking array or likelihood scores. The JSON schema requires all candidate keys. The strict parser additionally requires the rank values themselves to form an exact permutation of `1..20`. There is no tie-break, retry, or deterministic ranking repair.

Files:
- implementation: `src/pure_recommender/pure/recommender_rankmap.py`
- config: `config/phase5_pure_recommender_rankmap_pilot.toml`
- runner: `scripts/run_phase5_pure_recommender_rankmap_pilot.py`
- safe wrapper: `scripts/run_phase5_pure_recommender_rankmap_pilot_safe.py`
- tests: `tests/test_pure_recommender_rankmap.py`
