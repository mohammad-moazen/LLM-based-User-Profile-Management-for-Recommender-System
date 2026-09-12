# Project State

## Project
Step-by-step Python reproduction and local extension of PURE from the paper **LLM-based User Profile Management for Recommender System**.

## Current branch
`feature/pure-phase1`

## Current phase
**Phase 1 frozen / PASS. Local LLM infrastructure PASS. Phase 2 purchased-item baselines are historical PASS / FROZEN. Runtime profile `512 / 256 / 1` is finalized. Phase 3 Review Extractor clean-final attempt 1 reached 133/134; the single failure was diagnosed as a long structured-output case. A new homogeneous all-134 rerun is now configured with `max_tokens=1024`. Automatic Git handoff is active.**

The active model is the local derivative model `llama-3.2-3b-instruct-uncensored`; LM Studio reports GGUF `Q8_0` quantization and ~3.84 GB model size. Results are labeled **local derivative-model results**, not exact reproduction of the paper's `Llama-3.2-3B-Instruct` checkpoint.

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

The task is continuous next-item ranking: one ground-truth next item among 19 non-interacted negatives. NDCG is averaged across sessions within each user first, then across users.

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

100-request host-memory stability: PASS. The larger `1024 / 512 / 1` batch candidate was rejected because it was slower, used more RAM, and changed 2/12 sampled profile-safe outputs.

Important generation note: the Python API explicitly sends `temperature=0.0` and `seed=42`; LM Studio's Inference-tab temperature does not override those API values.

## Phase 2 purchased-item baselines — historical frozen results
- Sequential: NDCG@1/5/10/20 = 0.061667 / 0.182577 / 0.227799 / 0.366378
- Recency-Focused: 0.078333 / 0.199726 / 0.239947 / 0.378652
- ICL: 0.061667 / 0.186356 / 0.255724 / 0.371370

Before the final thesis comparison table, rerun compared methods under the finalized runtime/protocol rather than overwriting these historical records.

## Phase 3 Review Extractor
Accepted design:
- one canonical incoming interaction per LLM call;
- no future/target review leakage;
- evidence-backed JSON schema with `likes`, `dislikes`, `key_features`;
- audit-only normalized `value` plus review-grounded `evidence`;
- entry-level conservative evidence filtering;
- unsupported or blank evidence never enters profile-safe data;
- exact schema/grounding validator are explicit reproduction choices because the paper does not publish them.

### Historical development artifact
`outputs/phase3_review_extractor_v5/` reached 134/134 after resume/retry but is retained only as a development/audit artifact because prompt/schema behavior changed during its construction.

### Clean-final attempt 1 — 133/134
A new homogeneous run under the final prompt/schema/parser and finalized runtime used `max_tokens=512` in `outputs/phase3_review_extractor_final/`.

Result:
- successful: 133/134
- failed: 1
- failed task: `A2BFIYZYNK54QX:12`
- failure: malformed JSON model response
- accepted likes: 233
- accepted dislikes: 93
- accepted key features: 149
- rejected unsupported entries: 48
- total reported tokens: 95,600
- mean successful-request latency: 3.858 s

### Failed-task diagnostic
The failed task was rerun with the identical model/prompt/schema/parser/seed/temperature/runtime and only `max_tokens` increased from 512 to 1024.

Diagnostic result:
- finish reason: `stop`
- completion tokens: 495
- prompt tokens: 1,298
- total tokens: 1,793
- latency: 15.766 s
- parse status: PASS
- rejected entries: 0

Because the valid completion used 495 tokens, very close to the former 512-token ceiling, the 512 ceiling is considered too tight for the thesis-grade clean artifact. The exact backend budget mechanics are not claimed as proven.

Detailed diagnostic: `docs/PHASE3_FAILED_TASK_DIAGNOSTIC.md`.

### Clean-final attempt 2 — configured
To preserve homogeneity, do **not** patch only the failed row with a different ceiling. Instead all 134 tasks will be regenerated from scratch with:
- temperature: 0.0
- seed: 42
- max tokens: 1024
- same final prompt/schema/parser
- same finalized LM Studio runtime `512 / 256 / 1`
- new output directory: `outputs/phase3_review_extractor_final_1024/`

The previous v5 and 133/134 directories remain preserved for audit. Freeze Phase 3 only if the new clean run reaches 134/134.

## Runtime findings
- same-profile repeatability under `512 / 256 / 1`: 36/36 exact pairs, Jaccard 1.0
- fresh current-protocol 12-task reference mean latency: 3.838 s
- `1024 / 512 / 1` batch candidate mean latency: 4.025 s, exact matches 10/12, private RAM delta +0.710 GB — REJECTED

## Automatic experiment handoff
`handoff/latest.json` is a compact mailbox. Runners commit/push only this path, never README or unrelated local changes.

## Current implementation status
Completed:
- Phase 1 preprocessing/session/candidate freeze
- local inference infrastructure and RAM stability validation
- historical Sequential, Recency-Focused, ICL baselines
- Review Extractor implementation and grounding policy
- pilots v1-v5 and historical 134/134 development artifact
- deterministic repeatability characterization
- runtime profile benchmark and final selection `512 / 256 / 1`
- clean-final attempt 1 (133/134)
- failed-task 1024-token diagnostic PASS
- clean homogeneous 1024-token final rerun configured

## Next actions
1. Keep LM Studio on finalized `Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1` settings.
2. Pull the repository.
3. Run `python scripts/run_phase3_review_extractor_safe.py`.
4. The new output directory is empty, so all 134 tasks run from scratch with `max_tokens=1024`.
5. If 134/134 passes, freeze the homogeneous Review Extractor artifact and proceed to Profile Updater.

## Working rule
This file is the authoritative current snapshot. Raw datasets, processed artifacts, model weights, caches, and large outputs remain local and untracked.
