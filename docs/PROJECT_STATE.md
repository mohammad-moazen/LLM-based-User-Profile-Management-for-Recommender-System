# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 Sequential pilot is in prompt-validation/debugging.**

The user has explicitly chosen to continue with the currently available local derivative model `llama-3.2-3b-instruct-uncensored`. Phase 2 results produced with this model are valid project experiments but must be labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` backbone results.

## Environment
- Development: Python + VS Code
- Repository workflow: ChatGPT pushes incremental code to GitHub; user pulls and runs locally
- Local-only LLM inference; no online inference APIs
- Runtime: Bionic / LM Studio local OpenAI-compatible server
- Confirmed endpoint: `http://127.0.0.1:1234/v1`
- Backend abstraction: OpenAI-compatible HTTP client
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM

## Local LLM status
Confirmed:
- `GET /v1/models`: PASS
- Python chat completion through localhost: PASS
- localhost proxy interception bug fixed
- full regression suite before Sequential pilot: PASS

Active model:
- `llama-3.2-3b-instruct-uncensored`

Model policy: `docs/MODEL_RUNTIME_POLICY.md`.

## Dataset and frozen Phase 1
Dataset: Amazon Review Data 2018 / Video Games 5-core + metadata.

Frozen preprocessing policy: `docs/PREPROCESSING_POLICY.md`.

Frozen real-data result:
- raw reviews: 497,577
- final canonical interactions: 472,010
- final users: 55,209
- final items: 17,388
- eligible users with `min_history=3`: 54,451
- pilot users: 20
- frozen continuous recommendation sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

Core task: predict each eligible next purchase from one ground-truth item plus 19 non-interacted negatives. First target is cleaned purchase 4 because `min_history=3`.

## Phase 2 — Sequential baseline
Paper-derived behavior preserved:
- model sees only chronological purchased-item interactions and candidate list;
- reviews, ratings, profiles, and future items are excluded;
- target is never marked;
- frozen candidate sets from Phase 1 are reused;
- evaluate NDCG@1/@5/@10/@20;
- aggregate sessions within each user first, then average across users.

The paper does not publish the exact Sequential prompt or JSON schema. Our explicit protocol is documented in `docs/PHASE2_SEQUENTIAL_PROTOCOL.md`.

### Current implementation
- `config/phase2.toml`
- `src/pure_recommender/baselines/sequential.py`
- `src/pure_recommender/phase2/config.py`
- `src/pure_recommender/phase2/io.py`
- `scripts/run_phase2_sequential.py`
- `tests/test_sequential_baseline.py`

Initial pilot settings:
- first 3 frozen sessions
- temperature: 0.0
- max output tokens: 512
- generation seed: 42
- fail-fast: true
- resume: true

### First pilot attempt — formatting failure
Observed on session `A24ZRTTC3SPX8C:4`:
- history length: 3
- candidate count: 20
- parser error: `Ranking length 3 does not match candidate count 20`
- no NDCG result was accepted for this session
- failed record was written locally; resume will retry it because only `status="ok"` sessions are skipped

Diagnosis:
- the original prompt included a pseudo-JSON illustration with an ellipsis, conceptually like `{"ranking":["ASIN_1","ASIN_2",...,"ASIN_N"]}`;
- that is not valid JSON and can encourage a small local model to imitate a shortened three-entry structure;
- this is treated as a **prompt-formatting defect in our reproduction**, not a model-performance result.

Fix now pushed:
- removed placeholder/ellipsis pseudo-JSON from the prompt;
- prompt now states the exact required ranking length dynamically (`20` for the frozen pilot);
- explicitly forbids placeholders and ellipses;
- still requires a complete permutation of candidate ASINs with no silent repair;
- added regression test guarding against the placeholder pattern;
- runner now prints a raw model-response preview when parsing fails, while still preserving the full raw response in local results.

## Current implementation status
Completed:
- Phase 1 data/evaluation pipeline and real-data freeze
- local OpenAI-compatible inference infrastructure
- Sequential baseline runner, parser, metrics wiring, resume/checkpointing
- first real Phase 2 pilot attempt and diagnosis of output-formatting defect
- corrected exact-count JSON ranking prompt and regression coverage

Pending next:
1. Pull the prompt fix
2. Run the full unit-test suite
3. Re-run the same 3-session Sequential pilot
4. Confirm all three outputs contain complete 20-ASIN permutations
5. Inspect target ranks, latency, usage, and raw responses
6. If pilot passes, set `max_sessions = 0` and evaluate all 94 frozen sessions
7. Record Sequential NDCG@1/@5/@10/@20
8. Implement Recency and ICL baselines, then Review Extractor/PURE modules

## Working rule
This file is the authoritative snapshot of current project status. Important runs and failures belong in the experiment record; methodology decisions belong in dedicated policy/protocol documents. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
