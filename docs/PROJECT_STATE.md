# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 Sequential full run PASS / FROZEN. Recency-Focused baseline implemented and ready for a 3-session pilot.**

The user has explicitly chosen to continue with the local derivative model `llama-3.2-3b-instruct-uncensored`. Current Phase 2 metrics are therefore labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` backbone results.

## Environment
- Development: Python + VS Code
- Local-only inference through Bionic / LM Studio OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction: OpenAI-compatible HTTP client
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM

## Frozen Phase 1
Dataset: Amazon Review Data 2018 / Video Games 5-core + metadata.

Frozen real-data result:
- raw reviews: 497,577
- final canonical interactions: 472,010
- final users: 55,209
- final items: 17,388
- eligible users with `min_history=3`: 54,451
- pilot users: 20
- frozen sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

The task remains: use chronological history to rank one ground-truth next item among 19 non-interacted negatives. NDCG is averaged within user first, then across users.

## Local LLM status
Confirmed:
- `GET /v1/models`: PASS
- Python chat completion through localhost: PASS
- localhost proxy interception bug fixed
- validated numbered-candidate JSON ranking interface works end-to-end

Active model:
- `llama-3.2-3b-instruct-uncensored`

Model policy: `docs/MODEL_RUNTIME_POLICY.md`.

## Phase 2 — purchased-item baselines
Paper baselines reproduced in order:
1. Sequential — **PASS / FROZEN**
2. Recency-Focused — implemented, 3-session pilot pending
3. ICL — pending

The paper does not publish every exact prompt/output schema detail, so explicit reproduction choices are documented separately.

## Sequential baseline — frozen result
Protocol: `docs/PHASE2_SEQUENTIAL_PROTOCOL.md`

Result record: `docs/PHASE2_SEQUENTIAL_RESULTS.md`

Final full run:
- successful sessions: 94
- failed sessions: 0
- users: 20
- NDCG@1: 0.061667
- NDCG@5: 0.182577
- NDCG@10: 0.227799
- NDCG@20: 0.366378
- total tokens: 60,669
- mean latency: 1.385 seconds/session
- status: PASS

Sequential serialization after real-model debugging:
- history: canonical titles only;
- candidates: numbered titles only;
- model output: complete JSON permutation of candidate numbers 1..20;
- runner maps numbers back to unchanged frozen ASINs;
- malformed/incomplete/duplicate rankings are rejected, not repaired.

The two early formatting failures are retained as debugging evidence and are not included in the frozen metric.

## Recency-Focused baseline
Paper-derived distinction: use the Sequential setup but explicitly emphasize the most recently purchased item at time step `t-1`.

Protocol: `docs/PHASE2_RECENCY_PROTOCOL.md`

Implemented files:
- `config/phase2_recency.toml`
- `src/pure_recommender/baselines/recency.py`
- `scripts/run_phase2_recency.py`
- `tests/test_recency_baseline.py`

The Recency-Focused implementation preserves the exact frozen users, histories, targets, candidate sets, parser, metric, model, and generation settings from Sequential. Its only recommendation-behavior change is explicit recency emphasis in the prompt.

Initial Recency pilot settings:
- first 3 frozen sessions
- temperature: 0.0
- max output tokens: 512
- generation seed: 42
- resume: true
- fail-fast: true
- output directory: `outputs/phase2_recency/`

## Current implementation status
Completed:
- dataset schema inspection and anomaly analysis
- preprocessing-policy v1 freeze
- canonical preprocessing and audit reporting
- deterministic continuous sessions and candidate sampling
- NDCG metric and user-first aggregation
- Phase 1 synthetic and real-data validation
- local OpenAI-compatible client and proxy-safe transport
- local inference smoke test
- robust numbered-candidate output interface
- Sequential baseline 3-session pilot
- Sequential full 94-session run
- Sequential result freeze
- Recency-Focused prompt, config, runner, tests, and protocol documentation

Pending next:
1. Pull current changes.
2. Run the full unit-test suite.
3. Run `python scripts/run_phase2_recency.py` for the 3-session pilot.
4. If 3/3 pass, switch Recency to all 94 sessions and record NDCG@1/@5/@10/@20.
5. Freeze Recency-Focused.
6. Implement ICL using the paper's `t-2` history plus demonstrated recent item at `t-1`.
7. Then begin Review Extractor, Profile Updater, and full PURE.

## Working rule
This file is the authoritative current snapshot. Important experiment results are preserved in dedicated result/protocol documents. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
