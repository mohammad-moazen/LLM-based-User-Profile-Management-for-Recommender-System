# Phase 10A — Hardware Saturation Preflight Results

## Status

**PASS (benchmark completed) / TWO-WORKER CANDIDATE REJECTED**

No confirmatory-cohort LLM output was observed. Confirmatory LLM calls remain **0**.

## Phase 9 freeze verification

The preflight revalidated the frozen Phase 9 design before any synthetic request:

- users: 150
- sessions: 767
- cohort SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- sessions/candidates SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`

## Two-worker benchmark

- synthetic probes: 8
- sequential wall time: 27.7429 s
- two-worker wall time: 12.9188 s
- throughput speedup: **2.1475x**
- exact sequential/concurrent output matches: **5/8**
- exact-match rate: **62.5%**
- peak VRAM: **4463 MiB / 8188 MiB (54.5%)**
- peak GPU utilization: **100%**
- mean GPU utilization across sampled benchmark interval: **79.86%**
- peak recorded GPU power: **34.18 W**
- peak recorded temperature: **66 C**

## Decision

The two-worker profile is **rejected** despite the large throughput gain because concurrent execution did not preserve exact structured-output repeatability. The pre-declared acceptance policy required 100% exact canonical output agreement. Runtime scheduling is therefore frozen back to:

`Max Concurrent Predictions = 1`

for the confirmatory execution.

This decision is made before any confirmatory effectiveness output is inspected and is independent of NDCG.

## Hardware interpretation

The benchmark demonstrates that the RTX 4060 Laptop GPU is not VRAM-limited for these short-context requests: peak dedicated usage was only about 54.5%. Two concurrent requests were able to drive GPU utilization to 100% and roughly double throughput, but altered model outputs on 3 of 8 deterministic synthetic probes. For the confirmatory study, correctness/repeatability takes precedence over throughput.

The accepted single-worker runtime remains the previously validated profile:

- Context Length: 8192
- Max Concurrent Predictions: 1
- Evaluation Batch: 512
- Physical Batch: 256
- CPU threads: 7
- GPU Offload: maximum/all layers
- Unified KV: ON
- KV cache on GPU: ON
- Flash Attention: ON
- K/V quantization: OFF
- speculative decoding: OFF
- keep model in memory: ON
- mmap: ON

The earlier larger-batch runtime candidate (`1024/512/1`) had already been rejected for slower execution and weaker repeatability, so it is not reopened after seeing this benchmark.

## Scientific consequence

Phase 10 confirmatory execution will use the same one-at-a-time scheduling semantics as the frozen pilot. This sacrifices potential wall-clock speed but avoids introducing a runtime-dependent change in model ranking behavior.
