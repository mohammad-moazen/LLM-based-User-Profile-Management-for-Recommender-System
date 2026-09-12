# Phase 6A — Final Controlled Sequential Baseline Results

## Status

**PASS / FROZEN**

This is the authoritative Sequential result for the final thesis comparison. It replaces the earlier Phase 2 Sequential score only for the final controlled comparison table; the historical Phase 2 artifact remains preserved as a separate record.

## Experimental controls

- local derivative model: `llama-3.2-3b-instruct-uncensored`
- frozen workload: 20 users, 94 recommendation sessions
- candidate set: 20 frozen candidates per session
- candidate order: unchanged from frozen Phase 1
- method input: chronological purchase titles + frozen candidate titles only
- reviews, ratings, PURE profiles, target markers, and future information: excluded
- temperature: 0.0
- generation seed: 42
- max output tokens: 512
- primary output: direct complete numbered-candidate ranking
- fallback: one fresh Sequential rank-map request only after strict direct structural failure
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
| NDCG@1 | 0.07833333333333334 |
| NDCG@5 | 0.19119338415282436 |
| NDCG@10 | 0.22985864604036338 |
| NDCG@20 | 0.3732857741554989 |

Rounded for reporting:

- NDCG@1: **0.078333**
- NDCG@5: **0.191193**
- NDCG@10: **0.229859**
- NDCG@20: **0.373286**

## Usage and latency

- prompt tokens: 56,233
- completion tokens: 4,392
- total tokens: 60,625
- request count: 94
- mean prompt tokens/request: 598.2234
- max prompt tokens/request: 792
- mean completion tokens/request: 46.7234
- total request latency: 128.739 s
- mean request latency: 1.3696 s
- mean session latency: 1.3697 s
- median session latency: 1.3391 s

## Comparison with the historical Phase 2 Sequential result

Historical Sequential NDCG@1/5/10/20 was:

`0.061667 / 0.182577 / 0.227799 / 0.366378`

The final controlled rerun is:

`0.078333 / 0.191193 / 0.229859 / 0.373286`

The historical value must not be silently overwritten because the final rerun uses the finalized generation controls and hybrid output-validation contract, including an explicit generation seed that was not fixed in the original Phase 2 baseline run.

## Scientific labeling

These are results from the project's local derivative model and frozen 20-user evaluation subset. They are not an exact reproduction of the paper checkpoint or the paper's full-dataset numbers.
