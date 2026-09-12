# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines (Sequential, Recency-Focused, ICL) are PASS / FROZEN. Local runtime memory profile is stable. Phase 3 Review Extractor has a complete 134/134 historical accepted-output artifact, but a clean homogeneous final-protocol rerun is now required before thesis-grade downstream use. Runtime optimization is being benchmarked against the current final extractor protocol. Automatic Git handoff is active.**

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

## Local LLM/runtime status
Validated stable loader profile:
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

100-request host-memory stability test: PASS. Post-warm-up private RAM was 4.760 GB and final private RAM 4.761 GB; no sustained host-RAM growth was observed. Detailed record: `docs/RUNTIME_MEMORY_STABILITY.md`.

Important generation note: the Python API explicitly sends `temperature = 0.0` and `seed = 42` for current Phase 3 diagnostics. The LM Studio Inference-tab temperature shown in the UI does not override those API request values.

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

This was exposed by the runtime diagnostics: under the current final code, the same 12 tasks are 100% repeatable across three passes, yet only 8/12 match the historical stored rows exactly. The mismatch should therefore not be described as random generation variability.

Before Profile Updater is frozen, create one new clean Review Extractor output directory and rerun all 134 tasks under the final prompt/schema/validator and one finalized runtime profile. Do not overwrite the historical v5 artifact.

## Runtime repeatability diagnostic
Current unchanged loader profile: `Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1`.

Three repeated passes over the same 12 tasks (36 measured requests) produced:
- overall mean latency: 3.764 s
- overall median latency: 3.331 s
- pass means: 3.765, 3.764, 3.762 s
- exact repeat pairs: 36/36 = 100%
- mean/median/min pairwise Jaccard: 1.000 / 1.000 / 1.000
- each sampled task produced exactly one output variant across all 3 passes
- exact match vs historical Phase 3 rows: 8/12 on every pass
- mean Jaccard vs historical rows: 0.7994
- private RAM delta across diagnostic: -0.041 GB
- working-set delta: +0.051 GB

Conclusion: the **current inference path is deterministic/repeatable** for this sample. Historical mismatch is protocol-history drift, not ongoing same-profile randomness. Detailed record: `docs/RUNTIME_REPEATABILITY_BASELINE.md`.

## Runtime optimization protocol
Do not compare candidate loader settings directly against historical Phase 3 rows. Use the current final extractor code to capture a fresh baseline reference first.

New tool: `scripts/runtime_profile_reference.py`.

Baseline capture under `512 / 256 / 1`:

```powershell
python scripts/runtime_profile_reference.py capture --label baseline_512_256_1
```

Then, after changing only Evaluation Batch and Physical Batch, compare the candidate profile to that exact current-protocol reference. The first candidate to test is `1024 / 512 / 1`.

A candidate runtime profile is acceptable only if profile-safe outputs remain compatible with the fresh current-protocol reference, memory remains stable, and throughput improves. Context length, model/quantization, prompt/schema, K/V cache quantization, and scientific inputs are not changed for speed.

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

## Next actions
1. Keep LM Studio at `512 / 256 / 1` and capture a fresh current-protocol runtime reference.
2. Change only Evaluation Batch to 1024 and Physical Batch to 512; keep concurrency 1 and all scientific settings unchanged.
3. Compare candidate outputs/latency/RAM against the fresh reference.
4. If safe and faster, adopt/document the runtime profile; otherwise revert to `512 / 256 / 1`.
5. Perform one clean homogeneous 134-review extraction under the final protocol/runtime into a new output directory.
6. Freeze that homogeneous extractor artifact.
7. Implement and pilot Profile Updater chronologically with no future leakage.
8. Implement PURE recommender and evaluate on the frozen 94 sessions.
9. Rerun final compared baselines under the finalized runtime/protocol before the thesis comparison table.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
