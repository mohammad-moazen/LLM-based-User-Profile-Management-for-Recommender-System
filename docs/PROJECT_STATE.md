# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are historical PASS / FROZEN. Runtime profile `512 / 256 / 1` is finalized after the larger-batch candidate was rejected. Phase 3 Review Extractor now needs one clean homogeneous 134-review rerun under the final prompt/schema/parser and finalized runtime before downstream Profile Updater work. Automatic Git handoff is active.**

The active model is the local derivative model `llama-3.2-3b-instruct-uncensored`; LM Studio reports GGUF `Q8_0` quantization and ~3.84 GB model size. Results from this model are labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` checkpoint.

## Environment
- Development: Python + VS Code
- Local inference: LM Studio / llama.cpp OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`
- Hardware: Intel i7-13700H, 32 GB RAM, NVIDIA RTX 4060 Laptop GPU 8 GB VRAM
- repository workflow: ChatGPT pushes code/docs; user pulls/runs; experiment runners publish compact results through `handoff/latest.json`
- do not overwrite the user's local uncommitted README changes

## Frozen Phase 1
- raw reviews: 497,577
- final canonical interactions: 472,010
- final users: 55,209
- final items: 17,388
- eligible users: 54,451
- selected users: 20
- frozen continuous recommendation sessions: 94
- candidate size: 20
- candidate seed: 42
- candidate invariants: PASS

The task is continuous next-item ranking: one ground-truth next item among 19 non-interacted negatives. NDCG is averaged across sessions within each user first, then across users. Preprocessing decisions are in `docs/PREPROCESSING_POLICY.md`.

## Finalized local LLM/runtime profile
- Context Length: 8192
- GPU Offload: 28 / max
- CPU Thread Pool: 7
- Evaluation Batch Size: 512
- Physical Batch Size: 256
- Max Concurrent Predictions: 1
- Unified KV Cache: ON
- Context Checkpoints: 32
- KV Cache Offload to GPU: ON
- Keep Model in Memory: ON
- mmap: ON
- Speculative Decoding: OFF
- Flash Attention: ON
- K/V Cache Quantization: OFF

The 100-request host-memory stability test passed. Post-warm-up private RAM was 4.760 GB and final private RAM 4.761 GB; no sustained host-RAM growth was observed. Detailed record: `docs/RUNTIME_MEMORY_STABILITY.md`.

Important generation note: the Python API explicitly sends `temperature = 0.0` and `seed = 42` for current Phase 3 work. The LM Studio Inference-tab temperature shown in the UI does not override those API request values.

## Phase 2 purchased-item baselines — historical frozen results
### Sequential
- NDCG@1: 0.061667
- NDCG@5: 0.182577
- NDCG@10: 0.227799
- NDCG@20: 0.366378
- mean latency: 1.385 s/session

### Recency-Focused
- NDCG@1: 0.078333
- NDCG@5: 0.199726
- NDCG@10: 0.239947
- NDCG@20: 0.378652
- mean latency: 1.394 s/session

### ICL
- NDCG@1: 0.061667
- NDCG@5: 0.186356
- NDCG@10: 0.255724
- NDCG@20: 0.371370
- mean latency: 1.343 s/session

Comparison: `docs/PHASE2_BASELINE_COMPARISON.md`.

## Phase 3 Review Extractor
Accepted scientific design:
- one canonical incoming interaction per LLM call;
- no future/target review leakage;
- evidence-backed JSON schema with `likes`, `dislikes`, `key_features`;
- audit-only normalized `value` plus review-grounded `evidence`;
- entry-level conservative evidence filtering;
- unsupported or blank evidence never enters profile-safe data;
- exact schema/grounding validator are explicit project reproduction choices because the paper does not publish them.

### Historical development artifact — complete 134/134
The existing `outputs/phase3_review_extractor_v5/` directory reached:
- 134/134 successful tasks
- 0 failed
- accepted likes: 236
- accepted dislikes: 97
- accepted key features: 163
- total accepted entries: 496
- rejected unsupported/blank entries: 36
- total reported tokens: 92,829
- mean latency: 3.920 s/extraction

This artifact remains preserved for audit and documents the successful development path.

### Homogeneity correction
The first full run produced 131 successful rows under the pre-blank-evidence-fix prompt/schema. The blank-evidence patch then changed the active prompt/schema behavior and only the 3 failed tasks were regenerated via resume. Therefore the existing 134/134 directory is **not a homogeneous final-protocol run**, even though every stored profile-safe entry individually passed the accepted grounding validator.

Current-protocol repeatability testing showed 36/36 exact same-profile repeat pairs under `512 / 256 / 1`. Therefore the historical 8/12 mismatch against rerun outputs is protocol-history drift, not ordinary same-profile randomness.

A new clean output directory is now configured:

`outputs/phase3_review_extractor_final/`

The first run in this directory will generate all 134 tasks from scratch under one final prompt/schema/parser and the finalized runtime profile. The historical v5 directory is not overwritten.

## Runtime optimization findings
### Repeatability baseline — 512 / 256 / 1
Three repeated passes over the same 12 tasks (36 measured requests) produced:
- overall mean latency: 3.764 s
- exact repeat pairs: 36/36 = 100%
- mean/median/min pairwise Jaccard: 1.000 / 1.000 / 1.000

Detailed record: `docs/RUNTIME_REPEATABILITY_BASELINE.md`.

### Fresh current-protocol reference — 512 / 256 / 1
A fresh 12-task reference captured under the final extractor code produced:
- mean latency: 3.837574 s
- median latency: 3.400080 s
- rejected entries: 4
- total reported tokens: 8,271

### Candidate 1024 / 512 / 1 — REJECTED
Only Evaluation Batch and Physical Batch were increased. Result over the same 12 tasks:
- exact profile matches vs fresh reference: 10/12
- mean Jaccard: 0.909524
- minimum Jaccard: 0.2
- candidate mean latency: 4.024559 s
- reference mean latency: 3.837574 s
- speedup: 0.9535x, i.e. candidate was about 4.9% slower
- candidate private-RAM delta: +0.710 GB
- candidate working-set delta: +0.706 GB

Decision: **reject 1024 / 512 / 1**. It is slower, uses more memory, and changed profile-safe outputs for 2/12 sampled tasks. The project therefore finalizes `512 / 256 / 1` for the clean homogeneous extractor run and subsequent thesis-grade experiments. Detailed record: `docs/RUNTIME_PROFILE_CANDIDATE_1024_512_1.md`.

## Automatic experiment handoff
`handoff/latest.json` is a compact mailbox. Runners commit/push only this path, never README or unrelated local changes. Durable findings are moved into docs and the mailbox is reset between steps.

## Reproducibility note for final comparisons
The Phase 2 baseline scores are retained as historical frozen results. Before the final thesis comparison table, rerun compared methods under the finalized runtime profile and final protocol versions rather than overwriting historical records.

## Current implementation status
Completed:
- Phase 1 preprocessing/session/candidate freeze
- local inference infrastructure and RAM stability validation
- Sequential, Recency-Focused, ICL historical baseline freezes
- Review Extractor implementation, grounding policy, pilots v1-v5
- historical 134/134 Review Extractor completion
- deterministic current-profile repeatability characterization
- automatic Git handoff and traceback wrappers
- current-protocol runtime reference capture/compare tool
- 1024/512/1 runtime candidate benchmark and rejection
- final runtime profile selection: 512/256/1
- clean final extractor output directory configured

## Next actions
1. In LM Studio, restore Evaluation Batch Size to 512 and Physical Batch Size to 256; keep Max Concurrent Predictions at 1 and all other finalized settings unchanged.
2. Unload/reload the model so the restored loader profile is definitely active.
3. Pull the repository and run `python scripts/run_phase3_review_extractor_safe.py`.
4. Because the configured output directory is new, all 134 required reviews will be generated from scratch under one homogeneous final protocol/runtime.
5. Review the handoff; if 134/134 succeeds, freeze this homogeneous final Review Extractor artifact.
6. Implement and pilot Profile Updater chronologically with no future leakage.
7. Implement PURE recommender and evaluate on the frozen 94 sessions.
8. Rerun final compared baselines under the finalized runtime/protocol before the thesis comparison table.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
