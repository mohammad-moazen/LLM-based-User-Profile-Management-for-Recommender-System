# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 Sequential PASS / FROZEN. Recency-Focused PASS / FROZEN. ICL 3-session pilot PASS; full 94-session ICL run is now enabled.**

The user has explicitly chosen to continue with the local derivative model `llama-3.2-3b-instruct-uncensored`. Current Phase 2 metrics are therefore labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` backbone results.

## Environment
- Development: Python + VS Code
- Local-only inference through Bionic / LM Studio OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction: OpenAI-compatible HTTP client
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- Repository workflow: ChatGPT pushes incremental code/docs; user pulls, runs locally, and sends terminal results
- Do not overwrite the user's local uncommitted README changes

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

The task is continuous next-item ranking: for every eligible timestep, rank one ground-truth next item among 19 non-interacted negatives. NDCG is averaged across sessions within each user first, then averaged across users.

Frozen preprocessing decisions are documented in `docs/PREPROCESSING_POLICY.md`. These edge-case cleaning rules are reproduction choices, not paper-specified rules.

## Local LLM status
Confirmed:
- `GET /v1/models`: PASS
- Python chat completion through localhost: PASS
- localhost proxy interception bug fixed
- numbered-candidate JSON ranking interface validated across complete 94-session runs

Active model:
- `llama-3.2-3b-instruct-uncensored`

Model policy: `docs/MODEL_RUNTIME_POLICY.md`.

## Phase 2 purchased-item baselines
1. Sequential — **PASS / FROZEN**
2. Recency-Focused — **PASS / FROZEN**
3. In-Context Learning (ICL) — **3-session pilot PASS; full run enabled**

All three baselines reuse the same frozen users, sessions, candidate sets, targets, NDCG implementation, model, temperature, and generation seed. The baseline-specific difference is prompt framing.

## Shared robust output interface
After two early Sequential formatting failures, the stable interface is:
- purchase semantics are represented with canonical product titles;
- ASINs are hidden from the LLM prompt;
- current candidates are rendered as numbered titles (`Candidate 1` ... `Candidate 20`);
- model output is a JSON permutation of candidate numbers 1..20;
- runner maps candidate numbers back to the unchanged frozen candidate ASIN order;
- missing, duplicate, out-of-range, malformed, product-name, or ASIN outputs are rejected rather than repaired.

The two rejected formatting-debug attempts are not included in any reported NDCG.

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
- total reported tokens: 60,669
- mean latency: 1.385 seconds/session
- status: PASS

## Recency-Focused baseline — frozen result
Paper-derived distinction: same Sequential setup, with explicit emphasis on the most recently purchased item at time step `t-1`.

Protocol: `docs/PHASE2_RECENCY_PROTOCOL.md`

Result record: `docs/PHASE2_RECENCY_RESULTS.md`

Final full run:
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

Recency-Focused minus Sequential:
- NDCG@1: +0.016666 (~+27.03% relative)
- NDCG@5: +0.017149 (~+9.39% relative)
- NDCG@10: +0.012148 (~+5.33% relative)
- NDCG@20: +0.012274 (~+3.35% relative)
- total reported tokens: +4,008 (~+6.61%)
- mean latency: +0.009 seconds/session (~+0.65%)

This is a descriptive comparison for the current frozen local derivative-model pilot only.

## ICL baseline
Paper-derived framing for target timestep `t`:
- interactions through `t-2` are ordinary earlier history;
- the purchase at `t-1` is presented as an in-context demonstrated recommendation outcome;
- the model then ranks the current frozen candidate list for item `t`.

Protocol: `docs/PHASE2_ICL_PROTOCOL.md`

Implemented files:
- `config/phase2_icl.toml`
- `src/pure_recommender/baselines/icl.py`
- `scripts/run_phase2_icl.py`
- `tests/test_icl_baseline.py`

### Validated ICL pilot
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

These three-session metrics are diagnostic only and are not used as the final ICL performance estimate.

### Full ICL run configuration
Checked-in `config/phase2_icl.toml` now uses:
- `max_sessions = 0` -> all 94 frozen sessions
- `resume = true` -> the 3 successful pilot sessions are skipped automatically
- `fail_fast = false` -> one malformed response does not discard progress
- temperature: 0.0
- max output tokens: 512
- generation seed: 42

Invalid outputs remain excluded from NDCG. ICL is frozen only after all 94 sessions are successful and the summary reports `PASS`.

## Current implementation status
Completed:
- dataset schema/anomaly analysis and preprocessing-policy freeze
- canonical preprocessing and deterministic continuous session generation
- candidate leakage validation and NDCG/user-first aggregation
- Phase 1 real-data freeze
- local OpenAI-compatible client and inference smoke test
- robust numbered-candidate output serialization
- Sequential 94-session full run and result freeze
- Recency-Focused 94-session full run and result freeze
- ICL prompt builder, config, runner, tests, protocol documentation
- ICL 3-session real-data pilot: PASS

Pending next:
1. Pull the full-run ICL configuration.
2. Keep the local model server active.
3. Run `python scripts/run_phase2_icl.py` across all 94 frozen sessions.
4. If the summary is `INCOMPLETE`, rerun to retry only failed sessions and investigate persistent failures.
5. When 94/94 pass, freeze final ICL NDCG@1/@5/@10/@20, token usage, and latency.
6. Compare Sequential, Recency-Focused, and ICL on the same frozen pilot.
7. Then implement review-aware baselines and PURE components: Review Extractor, Profile Updater, and full recommender.

## Working rule
This file is the authoritative current snapshot. Important experiment results are preserved in dedicated result/protocol documents. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
