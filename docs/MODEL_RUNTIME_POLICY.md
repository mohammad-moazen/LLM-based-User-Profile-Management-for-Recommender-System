# Model and Local Runtime Policy

## Purpose
This document separates **runtime connectivity validation** from **paper-aligned model evaluation** so that a convenient local model used for a smoke test is never silently treated as the reference model from the PURE paper.

## Local-only inference rule
All LLM inference for the reproduction is local. No cloud inference API is used.

Preferred initial runtime:
- Bionic / LM Studio local OpenAI-compatible server
- localhost endpoint: `http://127.0.0.1:1234/v1`

The Python implementation must depend on an abstract OpenAI-compatible client rather than LM Studio-specific application logic. This allows a later switch to vLLM, llama.cpp, or another local compatible backend without rewriting PURE components.

## Reference reproduction model
The paper-aligned reference model is:

`Llama-3.2-3B-Instruct`

A Phase 2 or later result must not be labeled as the paper-aligned Llama reproduction unless the loaded model is the intended `Llama-3.2-3B-Instruct` checkpoint/variant. Quantization and runtime may differ for local feasibility, but must be recorded explicitly.

## Current local endpoint discovery
The local `/v1/models` endpoint has been confirmed reachable. Among the exposed model identifiers are:
- `llama-3.2-3b-instruct-uncensored`
- `qwen3-1.7b`
- at least one embedding model

The exact full list is runtime-local and may change as models are loaded/unloaded.

## Important distinction: smoke-test model vs experiment model
The currently exposed `llama-3.2-3b-instruct-uncensored` model is a derivative model and is **not** treated as identical to the paper's `Llama-3.2-3B-Instruct` reference model.

Policy:
1. It may be used for an HTTP/inference smoke test to validate Python -> localhost -> model execution.
2. Smoke-test output is infrastructure validation only and produces no paper-comparison metric.
3. Before Phase 2 Sequential baseline results are accepted as paper-aligned, load the intended `Llama-3.2-3B-Instruct` model and update the checked-in/local configuration accordingly.
4. Record model identifier, source/checkpoint description, quantization, context length, GPU offload, generation settings, backend/runtime version, and any relevant performance notes for every meaningful LLM experiment.

## Initial local model settings target
For the reference Llama reproduction, the current local target remains:
- model: `Llama-3.2-3B-Instruct`
- format/runtime: local model compatible with LM Studio/Bionic
- preferred initial quantization: GGUF `Q8_0`
- fallback if memory/performance requires: `Q6_K`, `Q5_K_M`, then `Q4_K_M`
- initial context length target: 8192 tokens
- temperature for deterministic ranking experiments: 0 where supported

These settings are reproduction/runtime choices and must not be attributed to the paper unless explicitly reported by the paper.

## Backend abstraction
Current code location:
- `src/pure_recommender/llm/client.py`
- `src/pure_recommender/llm/config.py`

The client currently supports the OpenAI-compatible endpoints needed for the project:
- `GET /v1/models`
- `POST /v1/chat/completions`

Phase 2 and PURE modules should call this abstraction rather than importing an LM Studio-specific SDK directly.
