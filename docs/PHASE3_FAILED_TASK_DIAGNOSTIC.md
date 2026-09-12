# Phase 3 Review Extractor — Failed-Task Diagnostic

## Context
The first clean homogeneous final-protocol run used the finalized runtime profile `Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1` and generation settings `temperature=0.0`, `seed=42`, `max_tokens=512`.

That run completed 133/134 required extractions. The only failed task was `A2BFIYZYNK54QX:12`, whose model response could not be parsed as valid JSON.

## Diagnostic
The failed task was replayed in isolation with the same:
- model: `llama-3.2-3b-instruct-uncensored`
- prompt and JSON schema
- grounding validator
- temperature: `0.0`
- seed: `42`
- finalized LM Studio runtime profile

Only the output ceiling was increased from 512 to 1024 tokens.

Result:
- task: `A2BFIYZYNK54QX:12`
- diagnostic max tokens: 1024
- finish reason: `stop`
- prompt tokens: 1,298
- completion tokens: 495
- total tokens: 1,793
- latency: 15.766 s
- parse status: PASS
- rejected entries: 0

The model therefore produced a complete valid structured response and stopped naturally. The 495-token completion is close to the former 512-token ceiling (about 96.7% of it), so the 512-token ceiling is considered too tight for the clean final artifact even though the exact backend token-budget mechanics cannot be proven from this diagnostic alone.

## Decision
Do not recover only the single failed row with a different generation ceiling, because that would make the final artifact heterogeneous.

Instead:
1. preserve the 133/134 clean-attempt directory for audit;
2. set Review Extractor `max_tokens=1024`;
3. use a new output directory `outputs/phase3_review_extractor_final_1024/`;
4. regenerate all 134 required extractions from scratch under the same final prompt/schema/parser/runtime and one identical 1024-token ceiling;
5. freeze only if the clean rerun reaches 134/134 successful.

This changes only the maximum allowed completion length, not prompt semantics, model identity, seed, temperature, candidate/session data, grounding rules, or loader profile.
