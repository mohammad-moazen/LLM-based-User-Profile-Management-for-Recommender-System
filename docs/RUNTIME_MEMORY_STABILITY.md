# Runtime Memory Stability Validation

## Purpose
This document records the host-RAM stability check performed before moving from the purchased-item baselines to longer review-aware PURE prompts.

## Hardware
- CPU: Intel Core i7-13700H
- System RAM: 32 GB
- GPU: NVIDIA RTX 4060 Laptop GPU, 8 GB VRAM

## Active local model
- Model identifier: `llama-3.2-3b-instruct-uncensored`
- Result label: local derivative-model runtime; not the paper's exact `Llama-3.2-3B-Instruct` checkpoint
- Backend: local LM Studio / llama.cpp OpenAI-compatible server
- Endpoint: `http://127.0.0.1:1234/v1`

## Validated LM Studio load settings
The memory-stability test was run after changing only runtime-throughput settings, while preserving model/context capacity:

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

These changes do not reduce the configured context window, alter model weights, or quantize the KV cache. They are runtime resource/throughput choices.

## Stress-test protocol
Script: `scripts/stress_test_llm_memory.py`

The test performs warm-up requests and then 100 repeated short local chat-completion requests while sampling the Windows `llama-server.exe` process memory. The interpretation focuses on the trend after warm-up rather than the initial allocation.

## Observed result
Final summary reported locally:

- post-warm-up private RAM: 4.760 GB
- final private RAM: 4.761 GB
- private RAM delta after warm-up: +0.000 GB at displayed precision
- working-set delta after warm-up: +0.000 GB at displayed precision
- mean request latency: 0.096 seconds
- status interpretation: stable plateau; no sustained cumulative host-RAM growth observed in this 100-request test

## Decision
The current runtime profile is accepted as the stable default for subsequent review-aware/PURE development.

No additional RAM-reduction measure should be introduced solely for memory pressure at this point. In particular, do not reduce context length, enable K/V cache quantization, or truncate scientific prompts merely to save memory unless a later real workload demonstrates a concrete need.

If future long-review workloads show renewed sustained private-RAM growth, repeat this test with the same process-level measurements before changing model-quality-relevant settings.

## Reproducibility note
The previously frozen Sequential, Recency-Focused, and ICL metrics were collected before this runtime-throughput profile was finalized. For thesis-grade direct quality comparisons against future PURE runs, a clean rerun of all compared methods under one common finalized runtime profile is preferred. Preserve the existing frozen results as historical records rather than overwriting them.
