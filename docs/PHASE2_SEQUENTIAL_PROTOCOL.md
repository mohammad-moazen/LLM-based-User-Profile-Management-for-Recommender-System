# Phase 2 Sequential Baseline Protocol

## Status
Active protocol for the 20-user / 94-session frozen Video Games pilot.

## Paper-derived setup
The PURE paper describes the **Sequential** baseline as an LLM recommender that receives only:
- the user's item interactions (purchased items), and
- the candidate list,

and ranks candidate items by their likelihood of being purchased at the current timestep.

The paper's continuous evaluation provides interaction history through timestep `t-1` and predicts the purchase at `t`, using a candidate set with one ground-truth item plus 19 randomly sampled non-interacted items. NDCG is averaged across sessions within each user first, then averaged across users.

The paper also states that JSON schemas are used to make generative outputs easier to parse reliably.

## Explicit reproduction choices not specified by the paper
The paper does not publish the exact Sequential baseline prompt text or its exact JSON schema. Our active Phase 2 protocol therefore fixes the following choices explicitly:

1. History is rendered oldest -> newest using canonical product titles only.
2. Reviews and ratings are excluded from the Sequential prompt.
3. History ASINs are not shown to the model. They are machine identifiers and add no semantic recommendation information.
4. Candidate items are rendered as prompt-local numbered choices, `Candidate 1` through `Candidate N`, with canonical product titles only.
5. Candidate ASINs are not shown to the model. The runner preserves the frozen candidate order and maps ranked candidate numbers back to their ASINs after parsing.
6. The target is never marked, highlighted, or otherwise revealed in the prompt.
7. The model is instructed to return exactly one valid JSON object with one key named `ranking`.
8. The `ranking` value must be a complete permutation of the candidate numbers. For the frozen pilot, it therefore contains each integer from 1 through 20 exactly once.
9. Digit-only JSON strings such as `"3"` are accepted as a serialization tolerance and normalized to integer 3. This does not infer, repair, add, remove, or reorder candidate choices.
10. Product names, ASINs, duplicate numbers, omitted numbers, or out-of-range numbers are rejected. Invalid rankings are never silently repaired.
11. Generation settings for the initial pilot are temperature `0.0`, maximum output length `512`, and request seed `42` where supported by the local backend.
12. The experiment is resumable and writes one result record after each attempted session. Failed records are retried because resume skips only sessions with `status="ok"`.

## Why the numbered-candidate protocol was adopted
Two early real-model pilot attempts exposed formatting failure modes in the original ASIN-output protocol:

- **Pilot attempt 1:** the prompt contained illustrative pseudo-JSON with an ellipsis. The local 3B model returned only 3 ranking entries instead of 20. This was treated as a prompt-formatting defect, not a recommendation result.
- **Pilot attempt 2:** after removing the ellipsis and explicitly requesting 20 ASINs, the model returned 23 ASINs: the 3 purchase-history ASINs followed by the 20 candidate ASINs. The model had copied machine identifiers from both prompt sections despite being told to rank candidates only.

The second failure showed that exposing ASINs in both history and candidate sections created unnecessary output ambiguity for the local model. ASINs carry no useful semantic recommendation content; the product titles do. Therefore, the active protocol separates semantic ranking from machine identifiers:

- history: titles only;
- candidates: numbered titles only;
- output: ranked candidate numbers only;
- evaluation: runner maps those numbers back to the unchanged frozen candidate ASIN list.

This changes only the serialization interface between prompt and parser. It does **not** change the frozen users, chronology, candidate sets, target items, or NDCG computation.

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
