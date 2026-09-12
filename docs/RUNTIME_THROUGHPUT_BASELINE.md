# Runtime Throughput Benchmark — Baseline 512/256/1

## Purpose
This benchmark measures the accepted local Review Extractor workload under the currently frozen LM Studio runtime profile before any throughput-oriented loader changes are tested.

Runtime profile represented by the label `baseline_512_256_1`:
- Evaluation Batch Size: 512
- Physical Batch Size: 256
- Max Concurrent Predictions: 1
- Context Length: 8192
- GPU Offload: max / 28
- Flash Attention: ON
- KV-cache quantization: OFF

The benchmark replays 12 evenly spaced frozen Review Extractor tasks without modifying the frozen Phase 3 outputs.

## Result
- model: `llama-3.2-3b-instruct-uncensored`
- measured tasks: 12
- warm-up requests: 2
- mean latency: 3.997 s
- median latency: 3.581 s
- min latency: 1.256 s
- max latency: 11.512 s
- historical mean latency for the same selected tasks: 3.675 s
- relative throughput vs historical selected tasks: 0.919x (this benchmark run was ~8.8% slower)
- exact profile matches vs frozen extraction: 8/12 = 66.7%
- total reported tokens: 8,272
- private RAM delta during benchmark: +0.004 GB
- working-set RAM delta during benchmark: +0.004 GB

## Interpretation
The RAM delta is negligible for this short run and does not indicate accumulating host-memory growth.

The important finding is that only 8 of 12 profile-safe extractions matched the previously frozen outputs exactly even though the model identifier, prompt, generation settings, seed, JSON schema, and loader profile were unchanged. Therefore strict exact-output equality cannot be treated as a standalone quality gate for future runtime-throughput comparisons.

Before testing a faster loader configuration, the project will measure same-profile run-to-run repeatability across several repeated passes over the same 12 tasks. This establishes the natural output and latency variability of the active local runtime. Future runtime tuning must be judged against that baseline variability rather than assuming bit-exact deterministic generation.

## Scientific status
This is a runtime diagnostic only. It does not replace, modify, or invalidate the frozen Phase 3 Review Extractor results. The frozen extractor remains 134/134 PASS under the accepted v5 grounding policy.
