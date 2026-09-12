# Phase 6C — Final Controlled ICL Baseline Results

## Status

**PASS / FROZEN**

This is the authoritative ICL result for the final thesis comparison. The earlier Phase 2 ICL result remains preserved as a historical artifact and is not overwritten.

## Experimental controls

- local derivative model: `llama-3.2-3b-instruct-uncensored`
- frozen workload: 20 users, 94 recommendation sessions
- candidate set: 20 frozen candidates per session
- candidate order: unchanged from frozen Phase 1
- method input: earlier purchase titles through `t-2` + the purchase at `t-1` presented as the demonstrated recommendation outcome + frozen candidate titles
- reviews, ratings, PURE profiles, target markers, and future information: excluded
- temperature: 0.0
- generation seed: 42
- max output tokens: 512
- primary output: direct complete numbered-candidate ranking
- fallback: one fresh ICL rank-map request only after strict direct structural failure
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
| NDCG@1 | 0.06166666666666667 |
| NDCG@5 | 0.184046153450114 |
| NDCG@10 | 0.24444677165894083 |
| NDCG@20 | 0.3687308921232335 |

Rounded for reporting:

- NDCG@1: **0.061667**
- NDCG@5: **0.184046**
- NDCG@10: **0.244447**
- NDCG@20: **0.368731**

## Usage and latency

- prompt tokens: 62,575
- completion tokens: 4,334
- total tokens: 66,909
- request count: 94
- mean prompt tokens/request: 665.6915
- max prompt tokens/request: 874
- mean completion tokens/request: 46.1064
- total request latency: 100.292 s
- mean request latency: 1.0669 s
- mean session latency: 1.0671 s
- median session latency: 1.0501 s

## Comparison with the historical Phase 2 ICL result

Historical ICL NDCG@1/5/10/20:

`0.061667 / 0.186356 / 0.255724 / 0.371370`

Final controlled rerun:

`0.061667 / 0.184046 / 0.244447 / 0.368731`

The historical value must not be silently replaced because the final rerun uses the finalized runtime/generation controls and hybrid output-validation contract, including an explicit generation seed that was not fixed in the original Phase 2 baseline run.

## Scientific labeling

These are results from the project's local derivative model and frozen 20-user evaluation subset. They are not an exact reproduction of the paper checkpoint or the paper's full-dataset numbers.
