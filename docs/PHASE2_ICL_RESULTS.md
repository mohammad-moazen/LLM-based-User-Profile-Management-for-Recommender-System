# Phase 2 ICL Baseline — Frozen Results

## Status
**PASS / FROZEN**

The purchased-item In-Context Learning (ICL) baseline completed all frozen Phase 1 recommendation sessions successfully.

## Experimental basis
- Dataset: Amazon Review Data 2018 / Video Games 5-core
- Frozen users: 20
- Frozen recommendation sessions: 94
- Candidate size: 20
- Same frozen targets/candidate sets as Sequential and Recency-Focused
- Model: `llama-3.2-3b-instruct-uncensored`
- Result label: local derivative-model result; not exact paper-checkpoint reproduction
- Temperature: 0.0
- Max output tokens: 512
- Generation seed: 42
- NDCG aggregation: sessions within user first, then users

## Final result
- successful sessions: 94
- failed sessions: 0
- users: 20
- NDCG@1: 0.061667
- NDCG@5: 0.186356
- NDCG@10: 0.255724
- NDCG@20: 0.371370
- total reported tokens: 66,877
- mean latency: 1.343 seconds/session
- status: PASS

## Completion note
The first full run reached 93/94 valid sessions. The local `llama-server.exe` process was then restarted to clear its accumulated process-local RAM/cache state without changing the model identifier or generation configuration. Because resume mode skips only successful sessions, the rerun retried the single failed session. The second summary reached 94/94 valid sessions and is the frozen ICL result above.

The earlier 93/94 summary is retained only as debugging/runtime history and is not the final ICL metric.

## ICL framing
For target timestep `t`:
- purchases through `t-2` are ordinary earlier history;
- purchase `t-1` is presented as a demonstrated recommendation outcome;
- the current frozen candidate set is ranked for purchase `t`;
- numbered candidate serialization and the shared strict parser are reused from the validated Sequential pipeline.

## Reproducibility note
These values are project results for the active local derivative model. They must not be reported as the exact numerical reproduction of the paper's `Llama-3.2-3B-Instruct` result.
