# Phase 2 In-Context Learning (ICL) Baseline Protocol

## Paper-derived behavior
The PURE paper describes the purchased-item ICL baseline as follows for prediction at time step `t`:
- user-item interactions are used only through time step `t-2`;
- the purchased item at time step `t-1` is presented as a demonstrated recommendation outcome;
- the prompt communicates that, after the earlier purchases, the recommender should have recommended the recent item, and now that the user has bought it the recommender should predict the next purchase.

Therefore ICL differs from both Sequential and Recency-Focused in how the observed history through `t-1` is framed:
- Sequential: all observed purchases through `t-1` are ordinary chronological context;
- Recency-Focused: same context, with explicit emphasis on `t-1`;
- ICL: purchases through `t-2` are ordinary context, while `t-1` is an in-context demonstrated next-item outcome.

## Active project implementation
For each frozen recommendation session targeting item `t`:
1. Load the same observed chronological history through `t-1` used by the other baselines.
2. Split it deterministically:
   - `history[:-1]` = earlier purchases through `t-2`;
   - `history[-1]` = demonstrated recent purchase at `t-1`.
3. Render only canonical product titles; reviews, ratings, timestamps, and ASINs are hidden from the LLM.
4. Present the recent item as the demonstrated outcome: after the earlier purchases, this is the item that should have been recommended; now that it has been bought, predict the next purchase.
5. Present the unchanged frozen current candidate set as `Candidate 1` through `Candidate 20` using product titles.
6. Require one JSON object whose `ranking` is a complete permutation of candidate numbers 1..20.
7. Map ranked candidate numbers back to the unchanged frozen candidate ASIN order for target-rank and NDCG computation.
8. Reject malformed, incomplete, duplicate, or out-of-range rankings rather than repairing them.

The exact wording and numbered-candidate JSON serialization are explicit reproduction choices because the paper describes the ICL framing but does not publish a complete machine-ready prompt/schema for our local runtime.

## Frozen experimental basis
- Dataset: Amazon Review Data 2018 / Video Games 5-core
- users: 20
- sessions: 94
- candidate size: 20
- same frozen Phase 1 targets and candidate sets as Sequential and Recency-Focused
- model: `llama-3.2-3b-instruct-uncensored`
- result label: local derivative-model result; not exact paper-checkpoint reproduction
- temperature: 0.0
- max output tokens: 512
- generation seed: 42
- NDCG cutoffs: 1, 5, 10, 20
- aggregation: sessions within user first, then users

## Real-data pilot result
The first 3 frozen sessions completed successfully:
- successful sessions: 3
- failed sessions: 0
- users represented: 2
- NDCG@1: 0.000000
- NDCG@5: 0.000000
- NDCG@10: 0.000000
- NDCG@20: 0.243320
- total reported tokens: 2,159
- mean latency: 1.439 seconds/session
- status: PASS

These values are retained only as a prompt/output validation pilot. Three sessions are too small for a substantive performance conclusion or comparison with the frozen Sequential and Recency-Focused baselines.

## Full-run sequence
The pilot gate is satisfied. Checked-in configuration now uses:
- `max_sessions = 0` to request all 94 frozen sessions;
- `resume = true` so the 3 successful pilot sessions are skipped;
- `fail_fast = false` so one malformed response does not discard progress on other sessions.

A full ICL result is frozen only when all 94 requested sessions have valid rankings and the final summary reports `PASS`.

## Relevant files
- `config/phase2_icl.toml`
- `src/pure_recommender/baselines/icl.py`
- `scripts/run_phase2_icl.py`
- `tests/test_icl_baseline.py`
- shared numbered parser/evaluation code from Sequential

## Output artifacts
Local-only outputs are written to:

`outputs/phase2_icl/`

Expected files:
- `results.jsonl`
- `summary.json`
