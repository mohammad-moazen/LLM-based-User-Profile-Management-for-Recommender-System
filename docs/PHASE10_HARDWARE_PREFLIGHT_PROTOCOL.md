# Phase 10A — Hardware Saturation Preflight Protocol

## Purpose

Phase 10A decides whether the confirmatory execution may safely use **two concurrent local LLM predictions** instead of the pilot runtime's single-prediction scheduling. This is done **before any confirmatory-cohort model output is observed**.

The goal is to increase GPU utilization and reduce wall-clock time without changing the scientific inputs, prompts, candidate sets, generation temperature, seed, token limits, model checkpoint, or output-validation rules.

## Why this is a separate preflight

The pilot/frozen runtime used `Max Concurrent Predictions = 1`. The confirmatory cohort is much larger: Phase 9 estimates roughly 3,676 LLM requests for the required PURE + Recency-Focused scope. Increasing concurrency may improve throughput on the RTX 4060 Laptop GPU, but it must not be adopted merely because it is faster.

A two-worker profile is accepted only if a synthetic benchmark shows:

1. exact canonical structured-output repeatability relative to sequential execution;
2. at least 1.15x wall-clock throughput improvement;
3. no benchmark failure;
4. peak measured VRAM use at or below 97% when `nvidia-smi` telemetry is available.

If any gate fails, Phase 10 keeps `Max Concurrent Predictions = 1`.

## Scientific isolation

The benchmark uses generated synthetic product/preference text only. It does **not** read or send to the LLM any of the following from the 150-user confirmatory cohort:

- reviews;
- ratings;
- profiles;
- target items;
- candidate titles or candidate sets;
- recommendation outcomes.

Therefore runtime scheduling is selected without inspecting confirmatory effectiveness data.

## Phase 9 freeze verification

Before the synthetic benchmark begins, the script recomputes and verifies:

- cohort SHA256: `72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca`
- sessions/candidates SHA256: `0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859`
- users: 150
- sessions: 767

Any mismatch aborts before an LLM request.

## Runtime settings held constant

Except for the temporary concurrency candidate, keep the accepted runtime profile unchanged:

- Context Length: 8192
- GPU Offload: maximum / all available layers
- Evaluation Batch: 512
- Physical Batch: 256
- CPU threads: 7
- Unified KV: ON
- KV cache on GPU: ON
- Flash Attention: ON
- K/V cache quantization: OFF
- speculative decoding: OFF
- keep model in memory: ON
- mmap: ON

Generation settings in the synthetic probe remain `temperature=0`, `seed=42`.

## User action before running

For this benchmark only, set **LM Studio Max Concurrent Predictions = 2**. Do not change any other model/runtime setting.

The script runs the same synthetic probes sequentially and then with two client workers. If LM Studio is still limited to one concurrent prediction, the two-worker section will effectively queue and will normally fail the minimum-speedup gate.

## Acceptance and freeze rule

- If accepted: Phase 10 execution will be implemented with two independent request workers where dependencies permit it. Profile updates remain sequential **within each user**, but separate users may run concurrently.
- If rejected: Phase 10 execution remains single-worker and the user's LM Studio Max Concurrent setting must be restored to 1.

No concurrency value is selected based on NDCG, ranking quality, or any confirmatory outcome.

## Output

Local output:

`outputs/phase10_hardware_preflight_v1/`

Files:

- `summary.json`
- `report.md`

A compact result is also published to `handoff/latest.json`.
