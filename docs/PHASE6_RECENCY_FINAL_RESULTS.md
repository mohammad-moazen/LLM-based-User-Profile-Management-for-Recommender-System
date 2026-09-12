# Phase 6B — Final Controlled Recency-Focused Baseline Results

## Status

**PASS / FROZEN**

This is the authoritative Recency-Focused result for the final thesis comparison. The earlier Phase 2 result remains preserved as a historical artifact and is not overwritten.

## Experimental controls

- local derivative model: `llama-3.2-3b-instruct-uncensored`
- frozen workload: 20 users, 94 recommendation sessions
- candidate set: 20 frozen candidates per session
- candidate order: unchanged from frozen Phase 1
- method input: chronological purchase titles + explicit emphasis on the most recent observed purchase + frozen candidate titles
- reviews, ratings, PURE profiles, target markers, and future information: excluded
- temperature: 0.0
- generation seed: 42
- max output tokens: 512
- primary output: direct complete numbered-candidate ranking
- fallback: one fresh Recency rank-map request only after strict direct structural failure
- post-generation repair: none
- NDCG aggregation: session scores averaged within user, then users averaged equally

## Final execution result

- requested sessions: 94
- successful sessions: 94
- failed sessions: 0
- users represented: 20
- direct-primary successes: 94
- fallback attempts: 0
- fallback successes: 0
- total LLM requests: 94
- status: **PASS / FROZEN**

## Final NDCG

| Metric | Score |
|---|---:|
| NDCG@1 | 0.095 |
| NDCG@5 | 0.20650509939667167 |
| NDCG@10 | 0.25295161727915483 |
| NDCG@20 | 0.3857992031968749 |

Rounded for reporting:

- NDCG@1: **0.095000**
- NDCG@5: **0.206505**
- NDCG@10: **0.252952**
- NDCG@20: **0.385799**

## Usage and latency

- prompt tokens: 60,224
- completion tokens: 4,479
- total tokens: 64,703
- request count: 94
- mean prompt tokens/request: 640.6809
- max prompt tokens/request: 849
- mean completion tokens/request: 47.6489
- total request latency: 161.877 s
- mean request latency: 1.7221 s
- mean session latency: 1.7223 s
- median session latency: 1.6696 s

## Comparison with the historical Phase 2 Recency result

Historical Recency-Focused NDCG@1/5/10/20:

`0.078333 / 0.199726 / 0.239947 / 0.378652`

Final controlled rerun:

`0.095000 / 0.206505 / 0.252952 / 0.385799`

The historical value must not be silently replaced because the final rerun uses the finalized runtime/generation controls and hybrid output-validation contract, including an explicit generation seed that was not fixed in the original Phase 2 baseline run.

## Scientific labeling

These are results from the project's local derivative model and frozen 20-user evaluation subset. They are not an exact reproduction of the paper checkpoint or the paper's full-dataset numbers.
