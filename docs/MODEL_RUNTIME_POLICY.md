# Model and Local Runtime Policy

## Purpose
This document separates **runtime connectivity validation**, **project experiments**, and **paper-aligned model reproduction** so that a convenient local model is never silently treated as the exact reference model from the PURE paper.

## Local-only inference rule
All LLM inference for the reproduction is local. No cloud inference API is used.

Preferred runtime:
- LM Studio / llama.cpp local OpenAI-compatible server
- localhost endpoint: `http://127.0.0.1:1234/v1`

The Python implementation depends on an abstract OpenAI-compatible client rather than LM Studio-specific application logic. This allows a later switch to vLLM, llama.cpp, or another local compatible backend without rewriting PURE components.

## Reference reproduction model
The paper-aligned reference model is:

`Llama-3.2-3B-Instruct`

A result must not be labeled as the paper's exact model reproduction unless the loaded model is the intended `Llama-3.2-3B-Instruct` checkpoint/variant. Quantization and runtime may differ for local feasibility, but must be recorded explicitly.

## Current local endpoint discovery
The local `/v1/models` endpoint has been confirmed reachable. Among the exposed model identifiers are:
- `llama-3.2-3b-instruct-uncensored`
- `qwen3-1.7b`
- at least one embedding model

End-to-end Python -> localhost -> chat completion has passed. The local HTTP client bypasses environment/system HTTP proxies so localhost requests remain direct.

## Active model decision
The user has explicitly chosen to continue the project with:

`llama-3.2-3b-instruct-uncensored`

This is a derivative model and is **not** treated as identical to the paper's `Llama-3.2-3B-Instruct` reference model.

Policy:
1. The derivative model may be used for Phase 2 and later project experiments.
2. Any metric produced with it must be labeled **local derivative-model result**, not exact paper-model reproduction.
3. The frozen Phase 1 data, chronological sessions, candidate sets, leakage rules, and NDCG aggregation remain unchanged; only the backbone model differs from the paper.
4. If the exact reference checkpoint is tested later, it will be reported as a separate paper-aligned run rather than silently replacing earlier results.
5. Record model identifier, source/checkpoint description when known, quantization, context length, GPU offload, generation settings, backend/runtime version, memory settings, and relevant performance notes for every meaningful LLM experiment.

## Finalized stable local runtime profile
Validated on the current hardware:
- CPU: Intel Core i7-13700H
- system RAM: 32 GB
- GPU: NVIDIA RTX 4060 Laptop GPU, 8 GB VRAM

LM Studio model-load settings:
- Context Length: 8192
- GPU Offload: 28 / maximum shown by the loader
- CPU Thread Pool Size: 7
- Evaluation Batch Size: 512
- Physical Batch Size: 256
- Max Concurrent Predictions: 1
- Unified KV Cache: enabled
- Context Checkpoints: 32
- Offload KV Cache to GPU Memory: enabled
- Keep Model in Memory: enabled
- `mmap`: enabled
- Speculative Decoding: off
- Flash Attention: enabled
- K Cache Quantization: off
- V Cache Quantization: off

Generation settings used by the experiment runners remain separate from model-load settings. For Phase 2 ranking runs they are:
- temperature: 0.0
- max output tokens: 512
- request seed: 42 where supported

The runtime profile deliberately preserves model/context capacity. Context length is not reduced and K/V cache quantization is not enabled merely to save memory.

## Host-memory stability validation
An earlier observation suggested that `llama-server.exe` host RAM grew across repeated experiment runs. Before applying more aggressive cache or context restrictions, the model was reloaded with the finalized runtime-throughput settings above and tested using `scripts/stress_test_llm_memory.py`.

Observed after warm-up over 100 repeated requests:
- post-warm-up private RAM: 4.760 GB
- final private RAM: 4.761 GB
- displayed private-RAM delta: +0.000 GB
- displayed working-set delta: +0.000 GB
- mean request latency: 0.096 seconds

Interpretation: the process reached a stable memory plateau in this controlled test. There is no evidence from this run of sustained cumulative host-RAM growth after warm-up.

Therefore:
1. Do not introduce additional RAM-saving changes solely because of the earlier cumulative-looking observation.
2. Do not reduce context length, quantize K/V cache, or truncate scientific prompts unless a later real workload demonstrates a concrete need.
3. If long review-aware prompts later cause renewed sustained growth, rerun the same process-level memory test before changing quality-relevant settings.
4. Server restarts between major experimental blocks are allowed, provided model/runtime/generation settings remain unchanged and the restart is documented.

Detailed result: `docs/RUNTIME_MEMORY_STABILITY.md`.

## Cross-experiment comparability
The currently frozen Sequential, Recency-Focused, and ICL results were produced before the finalized runtime-throughput profile above was locked down.

For thesis-grade final comparisons with future PURE/review-aware methods, prefer a clean rerun of all compared methods under one common finalized runtime profile. Existing frozen results must remain preserved as historical experiment records rather than being overwritten.

## Future exact-reference run
If an exact-reference run is added later:
- model: `Llama-3.2-3B-Instruct`
- preferred initial quantization: GGUF `Q8_0`
- fallback if memory/performance requires: `Q6_K`, `Q5_K_M`, then `Q4_K_M`
- initial context target: 8192 tokens

These runtime choices are reproduction decisions and must not be attributed to the paper unless explicitly reported there.

## Backend abstraction
Current code location:
- `src/pure_recommender/llm/client.py`
- `src/pure_recommender/llm/config.py`

The client currently supports:
- `GET /v1/models`
- `POST /v1/chat/completions`

Phase 2 and PURE modules call this abstraction rather than importing an LM Studio-specific SDK directly.

## Phase 2 protocol
Baseline-specific protocol and result documents are stored under `docs/` and distinguish paper-derived behavior from explicit reproduction choices.
