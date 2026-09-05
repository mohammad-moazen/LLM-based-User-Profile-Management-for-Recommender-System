# Experiment Log

Use this file as a chronological record of meaningful runs and debugging milestones. Do not overwrite past entries; append new entries.

## Entry template

### YYYY-MM-DD — <short experiment name>
- Git commit: `<sha>`
- Phase:
- Dataset/category:
- Data subset:
- Selection seed:
- Candidate seed:
- Model:
- Quantization:
- Context length:
- Temperature:
- Backend/runtime:
- Configuration:
- Number of users:
- Number of recommendation sessions:
- Metrics:
  - NDCG@1:
  - NDCG@5:
  - NDCG@10:
  - NDCG@20:
- Token/context statistics:
- Runtime/performance notes:
- Errors or anomalies:
- Interpretation:
- Next action:

## 2026-09-05 — Dataset schema inspection
- Phase: 0
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Review file: `Video_Games_5.json.gz`
- Metadata file: `meta_Video_Games.json.gz`
- Review file size observed locally: 146.84 MB
- Metadata file size observed locally: 50.81 MB
- First 1000 review records confirmed required fields: `reviewerID`, `asin`, `reviewText`, `overall`, `unixReviewTime`
- First 1000 metadata records confirmed required fields: `asin`, `title`
- Result: schema is suitable for the planned PURE data pipeline
- Next action: run full dataset validator and capture its summary here

## 2026-09-05 — Full Video Games dataset validation
- Phase: 0
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Review file: `Video_Games_5.json.gz`
- Metadata file: `meta_Video_Games.json.gz`
- Total metadata records: 84,819
- Unique metadata ASINs: 71,911
- Duplicate metadata ASIN rows: 12,908
- Metadata rows with empty title: 11
- Metadata missing required fields: 0
- Total review records: 497,577
- Unique users: 55,217
- Unique reviewed items: 17,408
- Review rows missing at least one required field: 158
- Empty review text rows: 0
- Review items missing from metadata lookup: 1,262
- Review-to-metadata title coverage: 99.7464%
- Repeated `(user, item)` rows: 24,149
- Users with at least 3 interactions: 55,211
- Users with at least 4 interactions: 55,210
- Users with at least 5 interactions: 55,200
- User history length: min=1, median=6, mean=9.01, p90=15, p95=20, max=815
- Rating distribution:
  - 1.0: 30,879
  - 2.0: 24,133
  - 3.0: 49,140
  - 4.0: 93,644
  - 5.0: 299,623
- Validation interpretation:
  - Dataset scale and chronological fields are sufficient for the planned sequential recommendation pipeline.
  - Metadata coverage is high enough for the initial implementation, but missing-title interactions must be handled deterministically.
  - Duplicate metadata ASINs and repeated user-item interactions are significant enough that their semantics must be inspected before final preprocessing rules are fixed.
  - A small number of users have fewer than five observed rows despite using the distributed 5-core file; the experiment pipeline will apply an explicit minimum-history eligibility rule rather than relying on the dataset label alone.
- Next action: inspect duplicate metadata records, repeated user-item interactions, missing-required review rows, and metadata misses; then freeze deterministic cleaning rules before producing processed data.

## 2026-09-05 — Dataset anomaly analysis and preprocessing-policy freeze
- Git commit containing anomaly-analysis script: `90194676eb3d15abd89b84cbfb98e88a3e6156c0`
- Phase: 0
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Metadata anomaly results:
  - total metadata rows: 84,819
  - unique ASINs: 71,911
  - duplicate ASINs: 12,908
  - duplicate ASIN groups with more than one distinct non-empty title: 0
  - rows with empty/invalid title: 11
- Review required-field results:
  - total review rows: 497,577
  - rows missing one or more required PURE fields: 158
  - observed examples are missing `reviewText`
- Review-to-metadata miss results:
  - review rows without a usable title: 1,262
  - unique affected ASINs: 19
  - most frequent missing-title ASIN: `B0016C3260` with 418 review rows
- Repeated `(user, item)` results:
  - unique pairs before cleaning: 473,427
  - repeated pairs: 23,937
  - rows beyond the first occurrence: 24,150
  - repeated pairs identical on PURE-relevant fields: 23,361
  - repeated pairs with different timestamp: 389
  - repeated pairs with different review text: 539
  - repeated pairs with different rating: 133
- Interpretation:
  - metadata duplicates are safe to collapse by ASIN because no duplicate group has conflicting non-empty titles
  - missing review text should not be imputed from `summary` in the primary reproduction
  - interactions without a usable metadata title should be removed from the canonical prompt/evaluation dataset
  - repeated user-item rows cannot safely be treated as repeated purchases because the review dataset does not establish purchase-event semantics
  - exact repeated user-item groups will therefore be collapsed; conflicting repeated pairs will be excluded conservatively from preprocessing-policy v1
- Policy status: frozen as `docs/PREPROCESSING_POLICY.md` v1
- Important provenance note: the PURE paper does not document these edge-case cleaning rules; they are explicit decisions in this reproduction and must be reported as such.
- Next action: implement the canonical processed-data pipeline exactly according to preprocessing-policy v1, then report post-cleaning counts before generating recommendation sessions.

## 2026-09-05 — Phase 1 implementation and synthetic validation
- Phase: 1
- Dataset/category: implementation tested with synthetic data only; real Video Games run pending
- Configuration defaults:
  - `min_history = 3`
  - `candidate_size = 20`
  - `candidate_seed = 42`
  - `user_selection_seed = 20260905`
  - `max_users = 20`
- Implemented:
  - canonical preprocessing-policy v1
  - chronological history construction with source-row tie-breaking
  - deterministic eligible-user subset selection
  - continuous recommendation-session generation beginning with purchase 4
  - one ground-truth item + 19 non-interacted negative candidates
  - full-history negative exclusion to prevent candidate leakage
  - deterministic candidate sampling and shuffling
  - NDCG@1/@5/@10/@20 helper logic
  - paper-style aggregation: mean across sessions within user, then mean across users
  - local compressed outputs for canonical items/interactions/sessions and JSON audit report
- Synthetic verification performed before push:
  - Python compilation: PASS
  - unit tests: 9/9 PASS
  - verified first target is interaction 4 when `min_history=3`
  - verified candidate sets are deterministic
  - verified negatives never overlap any item in the user's cleaned full history
  - verified NDCG rank discounts and equal-weight user aggregation
- Model/backend: not used in Phase 1
- Interpretation: Phase 1 implementation is ready for the first full local run against the downloaded Amazon files.
- Next action: run `python scripts/run_phase1.py` locally and append exact post-cleaning/session counts before freezing Phase 1.

## 2026-09-05 — First real Phase 1 session generation success
- Phase: 1
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Configuration: default `phase1.toml` settings (`min_history=3`, `candidate_size=20`, deterministic seeds, 20 selected users)
- Real local pipeline result: completed successfully through session generation.
- Observed first generated session:
  - session id: `A24ZRTTC3SPX8C:4`
  - user id: `A24ZRTTC3SPX8C`
  - observed history length: 3
  - target is the fourth cleaned interaction, confirming the intended `min_history=3` semantics
  - history consists of three gaming-keyboard purchases
  - target is a Logitech G502 gaming mouse
  - candidate set contains exactly 20 items
  - target appears exactly once in the candidate set, at displayed candidate position 17
  - remaining candidates are random non-interacted Video Games items, consistent with the current negative-sampling policy
- Pipeline status: `Phase 1 pipeline completed successfully.`
- Interpretation:
  - real-data chronology, target construction, candidate-set size, target inclusion, and deterministic candidate shuffling are functioning end-to-end
  - the sample is semantically plausible: a user with repeated gaming-keyboard purchases next buys a gaming mouse; the random negatives need not be semantically close because the paper samples random non-interacted items
  - Phase 1 is not yet formally frozen because the exact `PURE PHASE 1 REPORT` post-cleaning counts and generated-session counts still need to be recorded
- Next action: capture the `PURE PHASE 1 REPORT` summary from the same run, validate its final counts, then freeze Phase 1 and move to the local-model smoke test / Phase 2 Sequential LLM baseline.

## 2026-09-05 — Phase 1 real-data report and freeze
- Phase: 1
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Configuration:
  - `min_history = 3`
  - `candidate_size = 20`
  - `candidate_seed = 42`
  - selected users = 20
- Metadata audit:
  - raw metadata rows: 84,819
  - unique metadata ASINs: 71,911
  - duplicate ASIN groups collapsed: 12,908
  - metadata rows with empty titles: 11
- Review cleaning audit:
  - raw review rows: 497,577
  - rows dropped for missing required fields: 158
  - rows dropped for missing metadata/title: 1,262 across 19 ASINs
  - exact repeated `(user,item)` groups collapsed: 22,782
  - exact duplicate rows removed: 22,799
  - ambiguous repeated `(user,item)` groups excluded: 576
  - ambiguous rows excluded: 1,348
- Canonical dataset after preprocessing-policy v1:
  - final interactions: 472,010
  - final users: 55,209
  - final items: 17,388
  - users eligible for at least one session with `min_history=3`: 54,451
  - history length min: 1
  - history length median: 6.0
  - history length mean: 8.549511854951186
  - history length max: 775
- Session generation:
  - selected users: 20
  - generated sessions: 94
  - candidate size: 20
  - candidate seed: 42
  - candidate invariants: PASS
- Arithmetic consistency check:
  - `497,577 - 158 - 1,262 - 22,799 - 1,348 = 472,010`, exactly matching the reported final interaction count
- Interpretation:
  - the canonical preprocessing audit is internally consistent
  - real-data candidate invariants pass
  - the 20-user subset produced 94 continuous recommendation sessions, showing that multiple eligible timesteps per user are being generated as intended
  - Phase 1 has satisfied the agreed freeze criteria: deterministic preprocessing, chronology, target construction, candidate construction, leakage checks, NDCG infrastructure, unit tests, and a successful real-data run
- Status: **PHASE 1 FROZEN / PASS**
- Model/backend: not used in Phase 1
- Next action: configure and validate the local Bionic / LM Studio OpenAI-compatible endpoint using the local Llama-3.2-3B-Instruct model, then begin Phase 2 Sequential LLM baseline on the frozen Phase 1 sessions.

## 2026-09-05 — Local endpoint discovery and LLM client implementation
- Phase: infrastructure bridge between Phase 1 and Phase 2
- Backend/runtime: local OpenAI-compatible Bionic / LM Studio endpoint
- Endpoint confirmed reachable: `http://127.0.0.1:1234/v1`
- `/v1/models` discovery: PASS
- Exposed model identifiers observed include:
  - `llama-3.2-3b-instruct-uncensored`
  - `qwen3-1.7b`
  - at least one embedding model
- Model-policy interpretation:
  - `llama-3.2-3b-instruct-uncensored` is a derivative model and is accepted only for connectivity/inference smoke testing
  - it must not be reported as the paper's exact `Llama-3.2-3B-Instruct` reference model
  - paper-aligned Phase 2 metrics require the intended reference model to be loaded and its exact quantization/runtime settings documented
- Code added:
  - `src/pure_recommender/llm/client.py`: backend-agnostic standard-library OpenAI-compatible HTTP client
  - `src/pure_recommender/llm/config.py`: typed TOML config loader
  - `config/local_llm.toml`: localhost/model/generation smoke-test settings
  - `scripts/smoke_test_local_llm.py`: end-to-end Python -> local server -> model connectivity/inference test
  - `tests/test_llm_client.py`: local mock-server tests for `/v1/models` and `/v1/chat/completions`
  - `docs/MODEL_RUNTIME_POLICY.md`: explicit smoke-test vs paper-reference model policy
- Current configured smoke-test model: `llama-3.2-3b-instruct-uncensored`
- Smoke-test generation defaults:
  - temperature: 0.0
  - max tokens: 24
  - seed: 42 in the smoke-test request
- Local execution status: pending user pull/run
- Next action:
  1. run the full unit-test suite
  2. run `python scripts/smoke_test_local_llm.py`
  3. record response, latency, token usage, and any runtime issue
  4. load the exact `Llama-3.2-3B-Instruct` reference model before Phase 2 paper-aligned evaluation

## 2026-09-05 — Local LLM client regression fix and smoke-test PASS
- Phase: infrastructure bridge between Phase 1 and Phase 2
- Backend/runtime: local OpenAI-compatible Bionic / LM Studio endpoint
- Python version observed during test output: 3.12
- Initial regression symptom:
  - mock HTTP client tests returned HTTP 503 on a random localhost port
  - diagnosis: environment/system proxy handling could intercept localhost requests made by `urllib`
- Fix:
  - local LLM client now explicitly bypasses environment HTTP/HTTPS proxies for localhost inference
  - regression coverage added so local requests remain direct even when proxy variables are present
- Full unit-test suite after the fix: PASS (12 tests)
- End-to-end smoke test: PASS
- Smoke-test model: `llama-3.2-3b-instruct-uncensored`
- Smoke-test purpose: connectivity/inference validation only; no recommendation metric produced
- Confirmed path: Python -> localhost OpenAI-compatible endpoint -> local model -> valid completion
- Exact latency/token-usage values: not captured in the conversation record; preserve them from local terminal output if needed later
- Interpretation:
  - local inference infrastructure is now validated end-to-end
  - Phase 1 remains frozen and unaffected by the HTTP regression
  - the project is technically ready to implement Phase 2 logic, but paper-aligned Phase 2 metrics must wait until the intended `Llama-3.2-3B-Instruct` reference model is loaded and runtime settings are recorded
- Status: **LOCAL LLM INFRASTRUCTURE PASS**
- Next action:
  1. load the intended `Llama-3.2-3B-Instruct` reference model locally
  2. record exact model identifier, quantization, context length, GPU offload, runtime version, and generation settings
  3. re-run the smoke test using that exact model
  4. begin the Phase 2 Sequential baseline on the frozen 94-session pilot

## 2026-09-05 — Active derivative-model decision and Phase 2 Sequential implementation
- Phase: 2 / Sequential baseline preparation
- Dataset/category: Amazon Review Data 2018 / Video Games 5-core
- Frozen data basis: Phase 1 canonical dataset and 94 deterministic recommendation sessions
- User decision: continue with the currently available local model rather than blocking on loading a different checkpoint
- Active model: `llama-3.2-3b-instruct-uncensored`
- Model alignment label: **local derivative-model result; not exact paper-model reproduction**
- Paper-derived Sequential behavior preserved:
  - model sees only chronological purchased-item interactions and candidate list
  - reviews and ratings are excluded
  - candidate set remains the frozen 1-ground-truth + 19-non-interacted set from Phase 1
  - NDCG aggregation remains sessions-within-user first, then users
  - structured JSON output is used for post-processing
- Explicit reproduction choices because the paper does not publish exact Sequential prompt/schema:
  - history represented oldest -> newest as `title [ASIN]`
  - candidate represented as `title [ASIN]`
  - target is never marked in the prompt
  - expected JSON is `{"ranking":[...ASINs...]}`
  - ranking must be a complete permutation of candidates; malformed outputs are not silently repaired
- Phase 2 code added:
  - `config/phase2.toml`
  - `src/pure_recommender/baselines/sequential.py`
  - `src/pure_recommender/phase2/config.py`
  - `src/pure_recommender/phase2/io.py`
  - `scripts/run_phase2_sequential.py`
  - `tests/test_sequential_baseline.py`
  - `docs/PHASE2_SEQUENTIAL_PROTOCOL.md`
- Initial real-data pilot configuration:
  - max sessions: 3
  - temperature: 0.0
  - max output tokens: 512
  - generation seed: 42
  - fail-fast: true
  - resume/checkpoint: true
- Runner records per session:
  - model ranking
  - target rank
  - NDCG@1/@5/@10/@20
  - latency
  - reported token usage when available
  - raw model response
- Output directory: `outputs/phase2_sequential/` (Git-ignored)
- Metrics: pending local execution
- Interpretation: Phase 2 implementation is ready for a three-session real-data validation before running all 94 frozen sessions.
- Next action:
  1. pull the Phase 2 code
  2. run the full unit-test suite
  3. run `python scripts/run_phase2_sequential.py`
  4. inspect the three-session output and parser behavior
  5. if clean, switch `max_sessions` to 0 and evaluate all 94 frozen sessions
