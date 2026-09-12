# Runtime Profile Candidate: 1024 / 512 / 1

## Purpose
Evaluate whether increasing only LM Studio Evaluation Batch Size and Physical Batch Size can improve throughput without changing the current final Review Extractor protocol.

## Reference profile
- Evaluation Batch Size: 512
- Physical Batch Size: 256
- Max Concurrent Predictions: 1
- Context Length: 8192
- GPU Offload: 28 / max
- model: `llama-3.2-3b-instruct-uncensored`
- GGUF quantization reported by LM Studio: `Q8_0`
- temperature sent by API: 0.0
- seed sent by API: 42

Fresh current-protocol reference over 12 deterministic tasks:
- mean latency: 3.837574 s
- median latency: 3.400080 s
- rejected entries: 4
- total reported tokens: 8,271

## Candidate profile
Only the following loader values were changed:
- Evaluation Batch Size: 512 -> 1024
- Physical Batch Size: 256 -> 512
- Max Concurrent Predictions remained 1

All scientific inputs, prompt/schema/parser, model identity, context length, and cache quantization settings remained unchanged.

## Result
Candidate comparison over the same 12 tasks:
- exact profile matches: 10/12 (83.33%)
- mean Jaccard vs fresh reference: 0.909524
- median Jaccard: 1.0
- minimum Jaccard: 0.2
- candidate mean latency: 4.024559 s
- reference mean latency: 3.837574 s
- speedup vs reference: 0.9535x (candidate is about 4.9% slower)
- candidate rejected entries: 4
- reference rejected entries: 4
- candidate reported tokens: 8,305
- reference reported tokens: 8,271
- candidate private-RAM delta during test: +0.710 GB
- candidate working-set delta during test: +0.706 GB

Two sampled tasks changed profile-safe output under the candidate loader settings. Because the unchanged 512/256/1 profile was previously shown to be exactly repeatable across 36/36 same-profile repeat pairs, these changes are attributable to changing the loader execution profile rather than ordinary same-profile randomness in this diagnostic setup.

## Decision
**REJECTED.** The 1024/512/1 candidate is neither faster nor behavior-preserving for this test. It also uses substantially more host memory during the benchmark.

The project therefore retains `512 / 256 / 1` as the finalized runtime profile for the clean homogeneous Review Extractor rerun and subsequent thesis-grade experiments, unless a later independently validated runtime profile clearly improves throughput without compromising the accepted comparison criteria.
