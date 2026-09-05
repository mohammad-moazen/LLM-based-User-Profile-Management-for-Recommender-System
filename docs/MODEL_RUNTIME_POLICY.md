# Model and Local Runtime Policy

## Purpose
This document separates **runtime connectivity validation**, **project experiments**, and **paper-aligned model reproduction** so that a convenient local model is never silently treated as the exact reference model from the PURE paper.

## Local-only inference rule
All LLM inference for the reproduction is local. No cloud inference API is used.

Preferred initial runtime:
- Bionic / LM Studio local OpenAI-compatible server
- localhost endpoint: `http://127.0.0.1:1234/v1`

The Python implementation must depend on an abstract OpenAI-compatible client rather than LM Studio-specific application logic. This allows a later switch to vLLM, llama.cpp, or another local compatible backend without rewriting PURE components.

## Reference reproduction model
The paper-aligned reference model is:

`Llama-3.2-3B-Instruct`

A result must not be labeled as the paper's exact model reproduction unless the loaded model is the intended `Llama-3.2-3B-Instruct` checkpoint/variant. Quantization and runtime may differ for local feasibility, but must be recorded explicitly.

## Current local endpoint discovery
The local `/v1/models` endpoint has been confirmed reachable. Among the exposed model identifiers are:
- `llama-3.2-3b-instruct-uncensored`
- `qwen3-1.7b`
- at least one embedding model

The exact full list is runtime-local and may change as models are loaded/unloaded.

End-to-end Python -> localhost -> chat completion has also passed. The local HTTP client bypasses environment/system HTTP proxies so localhost requests remain direct.

## Active model decision
The user has explicitly chosen to continue the project with the currently available model:

`llama-3.2-3b-instruct-uncensored`

This is a derivative model and is **not** treated as identical to the paper's `Llama-3.2-3B-Instruct` reference model.

Policy from this point forward:
1. The derivative model may be used for Phase 2 and later project experiments.
2. Any metric produced with it must be labeled **local derivative-model result**, not exact paper-model reproduction.
3. The frozen Phase 1 data, chronological sessions, candidate sets, leakage rules, and NDCG aggregation remain unchanged; only the backbone model differs from the paper.
4. If the exact reference checkpoint is tested later, it will be reported as a separate paper-aligned run rather than silently replacing earlier results.
5. Record model identifier, source/checkpoint description when known, quantization, context length, GPU offload, generation settings, backend/runtime version, and relevant performance notes for every meaningful LLM experiment.

## Initial local settings target
For the currently active local experiments:
- model identifier: `llama-3.2-3b-instruct-uncensored`
- runtime: local OpenAI-compatible Bionic / LM Studio server
- endpoint: `http://127.0.0.1:1234/v1`
- deterministic ranking temperature: `0.0` where supported
- Phase 2 ranking max output tokens: `512`
- request seed: `42` where supported

For a future exact-reference run, the prior target remains:
- model: `Llama-3.2-3B-Instruct`
- preferred initial quantization: GGUF `Q8_0`
- fallback if memory/performance requires: `Q6_K`, `Q5_K_M`, then `Q4_K_M`
- initial context length target: 8192 tokens

These runtime choices are reproduction decisions and must not be attributed to the paper unless explicitly reported there.

## Backend abstraction
Current code location:
- `src/pure_recommender/llm/client.py`
- `src/pure_recommender/llm/config.py`

The client currently supports the OpenAI-compatible endpoints needed for the project:
- `GET /v1/models`
- `POST /v1/chat/completions`

Phase 2 and PURE modules call this abstraction rather than importing an LM Studio-specific SDK directly.

## Phase 2 protocol
The current Sequential-baseline protocol and the distinction between paper-derived behavior and our explicit prompt/JSON choices are documented in:

`docs/PHASE2_SEQUENTIAL_PROTOCOL.md`
