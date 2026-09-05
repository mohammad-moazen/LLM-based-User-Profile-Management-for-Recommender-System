# Phase 2 Sequential Baseline Protocol

## Status
Initial protocol for the 20-user / 94-session frozen Video Games pilot.

## Paper-derived setup
The PURE paper describes the **Sequential** baseline as an LLM recommender that receives only:
- the user's item interactions (purchased items), and
- the candidate list,

and ranks candidate items by their likelihood of being purchased at the current timestep.

The paper's continuous evaluation provides interaction history through timestep `t-1` and predicts the purchase at `t`, using a candidate set with one ground-truth item plus 19 randomly sampled non-interacted items. NDCG is averaged across sessions within each user first, then averaged across users.

The paper also states that JSON schemas are used to make generative outputs easier to parse reliably.

## Explicit reproduction choices not specified by the paper
The paper does not publish the exact Sequential baseline prompt text or its exact JSON schema. Our v1 Phase 2 protocol therefore fixes the following choices explicitly:

1. History is rendered oldest -> newest.
2. Each purchased item is represented by canonical product title plus ASIN.
3. Reviews and ratings are excluded from the Sequential prompt.
4. Candidate items are represented by canonical product title plus ASIN.
5. The target is never marked, highlighted, or otherwise revealed in the prompt.
6. The model is instructed to return one JSON object:
   `{"ranking":["ASIN_1",...,"ASIN_20"]}`
7. A response is valid only if `ranking` is a complete permutation of all 20 candidate ASINs: no omissions, no duplicates, and no out-of-candidate items.
8. Invalid rankings are not silently repaired. The initial pilot is fail-fast so malformed output can be inspected before a larger run.
9. Generation settings for the initial pilot are temperature `0.0`, maximum output length `512`, and request seed `42` where supported by the local backend.
10. The experiment is resumable and writes one result record after each completed session.

## Active model decision
The user has explicitly chosen to continue with the currently available local model:

`llama-3.2-3b-instruct-uncensored`

This is a derivative local model. Results obtained with it are valid project experiments but must be labeled **local derivative-model results**, not exact reproduction of the paper's reported `Llama-3.2-3B-Instruct` backbone results.

This model choice does not change the frozen Phase 1 data, candidate sets, chronology, or evaluation metric.

## Pilot sequence
1. Run all unit tests.
2. Run the first **3** frozen real sessions (`max_sessions = 3`).
3. Inspect parser success, target ranks, latency, token usage, and raw outputs.
4. If all three are valid, change `max_sessions = 0` and run all **94** frozen sessions.
5. Report NDCG@1, NDCG@5, NDCG@10, and NDCG@20 with paper-style per-user aggregation.
6. Only after the Sequential baseline is stable proceed to Recency, ICL, and PURE components.

## Relevant code
- `config/phase2.toml`
- `src/pure_recommender/baselines/sequential.py`
- `src/pure_recommender/phase2/config.py`
- `src/pure_recommender/phase2/io.py`
- `scripts/run_phase2_sequential.py`
- `tests/test_sequential_baseline.py`

## Output artifacts
Local-only outputs are written under:

`outputs/phase2_sequential/`

Expected files:
- `results.jsonl`: append-only per-session model results, ranks, NDCG values, usage, latency, and raw response
- `summary.json`: aggregate run summary and paper-style NDCG metrics

The output directory remains excluded from Git.
