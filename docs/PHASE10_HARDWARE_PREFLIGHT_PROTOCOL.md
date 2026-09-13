# Phase 10A — Hardware Saturation Preflight Protocol

## Purpose

Phase 10A decides whether the confirmatory execution may safely use **two concurrent local LLM predictions for short-context components** instead of the pilot runtime's single-prediction scheduling. This is done **before any confirmatory-cohort model output is observed**.

The goal is to increase GPU utilization and reduce wall-clock time without changing the scientific inputs, prompts, candidate sets, generation temperature, seed, token limits, model checkpoint, or output-validation rules.

## Attempt 1 and context-capacity boundary

The first synthetic attempt used 220 generated history lines. Sequential synthetic requests fit, but the two-worker section failed with the local engine error `Context size has been exceeded.` The safe wrapper confirmed `confirmatory_llm_calls = 0`.

This establishes an important runtime boundary: two concurrent slots must not be assumed safe for long prompts under the frozen Context Length 8192 profile. In particular, the accepted pilot Profile Updater previously reached a 4,287-token prompt with a 1,024-token output ceiling. Therefore Profile Updater concurrency remains **1**, regardless of the revised short-context benchmark result.

The failure and revision are documented in `docs/PHASE10_HARDWARE_PREFLIGHT_ATTEMPT1.md`.

## Revised short-context probe

The revised benchmark uses 70 synthetic history lines and a 1,024-token generation ceiling. It remains unrelated to the confirmatory users and exists only to test whether two concurrent short-context requests can improve throughput safely.

A two-worker short-context profile is accepted only if the synthetic benchmark shows:

1. exact canonical structured-output repeatability relative to sequential execution;
2. at least 1.15x wall-clock throughput improvement;
3. no benchmark failure;
4. peak measured VRAM use at or below 97% when `nvidia-smi` telemetry is available.

If any gate fails, all Phase 10 LLM components remain single-worker.

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

Except for the temporary short-context concurrency candidate, keep the accepted runtime profile unchanged:

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

## User action before running revised preflight

For the revised benchmark only, set **LM Studio Max Concurrent Predictions = 2**. Do not change any other model/runtime setting.

The script runs the same synthetic probes sequentially and then with two client workers. If LM Studio is still limited to one concurrent prediction, the two-worker section will effectively queue and will normally fail the minimum-speedup gate.

## Acceptance and Phase 10 scheduling rule

If the revised short-context probe is accepted, Phase 10 will use staged scheduling rather than one concurrency setting for every component:

- Review Extractor: eligible for two-worker execution after the accepted probe;
- Profile Updater: **single-worker only** because it is long-context and sequential within each user;
- Recency-Focused recommender: eligible for two-worker execution;
- PURE recommender: concurrency will remain conservative unless its generated profile prompts are shown, before ranking execution, to fit the short-context budget with adequate headroom; otherwise it remains single-worker.

This component-specific scheduling is a computational optimization only. It does not change prompts, model, seed, temperature, candidate order, profile policy, ranking parser, or endpoint.

If the revised probe is rejected, the complete Phase 10 confirmatory execution remains single-worker and LM Studio Max Concurrent Predictions must be restored to 1.

No concurrency value is selected based on NDCG, ranking quality, or any confirmatory outcome.

## Output

Attempt 1 local output:

`outputs/phase10_hardware_preflight_v1/`

Revised attempt local output:

`outputs/phase10_hardware_preflight_v1_attempt2/`

The revised run writes `summary.json` and `report.md`, and publishes a compact result to `handoff/latest.json`.
