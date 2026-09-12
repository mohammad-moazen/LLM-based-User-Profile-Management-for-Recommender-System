# Phase 2 Recency-Focused Baseline Protocol

## Status
**PASS / FROZEN** for the 20-user / 94-session Video Games pilot.

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

## Validation sequence completed
1. First 3 frozen real sessions: 3/3 valid rankings, PASS.
2. Full run enabled with `max_sessions = 0`, resume, and non-fail-fast execution.
3. All 94 frozen sessions completed with valid rankings and zero failures.
4. Final result frozen in `docs/PHASE2_RECENCY_RESULTS.md`.

## Final frozen result
- successful sessions: 94
- failed sessions: 0
- users: 20
- NDCG@1: 0.078333
- NDCG@5: 0.199726
- NDCG@10: 0.239947
- NDCG@20: 0.378652
- total reported tokens: 64,677
- mean latency: 1.394 seconds/session
- status: PASS

## Relevant files
- `config/phase2_recency.toml`
- `src/pure_recommender/baselines/recency.py`
- `scripts/run_phase2_recency.py`
- `tests/test_recency_baseline.py`
- shared parser/evaluation from the validated Sequential implementation
- `docs/PHASE2_RECENCY_RESULTS.md`

## Output artifacts
Local-only outputs are written to:

`outputs/phase2_recency/`

Expected files:
- `results.jsonl`
- `summary.json`

Next purchased-item baseline: **In-Context Learning (ICL)**.
