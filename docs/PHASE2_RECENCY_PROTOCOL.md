# Phase 2 Recency-Focused Baseline Protocol

## Paper-derived behavior
The PURE paper defines **Recency-Focused** as the Sequential prompt plus an instruction that emphasizes the most recently purchased item at time step `t-1`. The paper gives the additional instruction conceptually as:

`Note that my most recently purchased item is {recent item}.`

Therefore, relative to the frozen Sequential baseline, Recency-Focused changes only the prompt emphasis. It does not change the chronological history, candidate set, target, model, or metric.

## Active project implementation
The validated numbered-candidate serialization from Sequential is retained:
- chronological purchase history is shown as canonical product titles only;
- the most recent title is also explicitly repeated in a recency-emphasis sentence;
- reviews and ratings are excluded;
- history ASINs are hidden from the model;
- candidates are shown as `Candidate 1` through `Candidate 20` with product titles only;
- candidate ASINs remain internal and are mapped from ranked candidate numbers after parsing;
- output must be one JSON object with a complete permutation of integers 1..20;
- invalid rankings are rejected rather than repaired.

This preserves the same output interface that completed all 94 Sequential sessions without formatting errors while implementing the paper's Recency-Focused distinction.

## Frozen experimental basis
- Dataset: Amazon Review Data 2018 / Video Games 5-core
- users: 20
- sessions: 94
- candidate size: 20
- same Phase 1 candidate sets as Sequential
- model: `llama-3.2-3b-instruct-uncensored`
- result label: local derivative-model result; not exact paper-checkpoint reproduction
- temperature: 0.0
- max output tokens: 512
- generation seed: 42
- NDCG cutoffs: 1, 5, 10, 20
- aggregation: sessions within user first, then users

## Real-data pilot result
The first 3 frozen sessions completed successfully under the Recency-Focused prompt:
- successful sessions: 3
- failed sessions: 0
- users represented: 2
- NDCG@1: 0.250000
- NDCG@5: 0.250000
- NDCG@10: 0.250000
- NDCG@20: 0.443641
- total reported tokens: 2,085
- mean latency: 1.399 seconds/session
- status: PASS

These values are retained as a prompt/output validation pilot only. Three sessions are too small for a substantive performance conclusion or comparison with the frozen Sequential result.

## Full-run sequence
The pilot gate is satisfied. Checked-in configuration now uses:
- `max_sessions = 0` to request all 94 frozen sessions;
- `resume = true` so the 3 successful pilot sessions are skipped;
- `fail_fast = false` so one malformed response does not discard progress on other sessions.

A full Recency-Focused result is frozen only when all 94 requested sessions have valid rankings and the final summary reports `PASS`.

## Relevant files
- `config/phase2_recency.toml`
- `src/pure_recommender/baselines/recency.py`
- `scripts/run_phase2_recency.py`
- `tests/test_recency_baseline.py`
- shared parser/evaluation from the validated Sequential implementation

## Output artifacts
Local-only outputs are written to:

`outputs/phase2_recency/`

Expected files:
- `results.jsonl`
- `summary.json`
