# Phase 10A — Hardware Preflight Attempt 1

## Status

**INFRASTRUCTURE REJECT / NO CONFIRMATORY OUTCOME EXPOSURE**

Attempt 1 was a synthetic-only hardware benchmark. It verified the frozen Phase 9 manifests before any model request and did not submit any review, profile, candidate, target, or recommendation content from the 150-user confirmatory cohort to the LLM.

The run failed during the two-worker synthetic section with the local engine error:

`Context size has been exceeded.`

The safe wrapper reported `confirmatory_llm_calls = 0`.

## Interpretation

This failure is useful runtime evidence rather than an effectiveness result. With Context Length 8192 and LM Studio Max Concurrent Predictions set to 2, the original long synthetic probe (220 generated history lines) was too large for the engine's concurrent context allocation.

Therefore two-worker scheduling is **not** authorized for long-context components such as the Profile Updater. The accepted pilot Profile Updater already observed a maximum prompt of 4,287 tokens with a 1,024-token output ceiling, so forcing that component into the two-worker profile would create avoidable context-risk.

## Prospective revision before confirmatory execution

Because no confirmatory outcome was observed, the preflight is revised only for a short-context concurrency decision:

- keep Context Length 8192 unchanged;
- keep all model/generation settings unchanged;
- keep Max Concurrent Predictions at 2 only for the revised synthetic test;
- reduce synthetic history from 220 to 70 lines;
- use a 1,024-token output ceiling in the probe;
- require the same exact-output, throughput and VRAM gates;
- never infer from a successful short-context probe that the Profile Updater can run with two concurrent slots.

If the revised probe passes, Phase 10 may use concurrency only for components whose prompt/output budget is demonstrably compatible with the short-context lane. Long-context Profile Updater execution remains single-worker. If the revised probe fails, the complete confirmatory pipeline remains single-worker.

## Scientific boundary

This revision is based solely on a runtime capacity error observed before any confirmatory-cohort LLM output. It does not change the frozen users, sessions, candidates, model, prompts, endpoint, primary comparison, NDCG@10 endpoint, alpha, or analysis rule.
