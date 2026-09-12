# Phase 5 PURE Recommender — Hybrid Pilot v4

## Purpose

This pilot tested one predefined conditional serialization policy on the same eight diagnostic sessions used by the scored-output and rank-map pilots.

Policy for every session:
1. request the direct 20-candidate ranking array;
2. validate it with the strict complete-permutation parser;
3. only after a structural direct-ranking parser failure, discard the invalid response and issue one fresh rank-map request using the same frozen history, profile, candidates, model, temperature, seed, and token cap;
4. do not show the invalid direct response to the fallback request;
5. do not perform deterministic post-generation repair.

The goal was to exploit the complementary behavior observed previously: direct ranking had failed on two sessions for which rank-map had succeeded, while standalone rank-map had failed on two sessions that direct ranking handled successfully.

## Result

Execution result:
- requested sessions: 8
- successful sessions: 8
- failed sessions: 0
- users represented: 4
- direct-primary successes: 7
- fallback attempts: 1
- fallback successes: 1
- deterministic post-generation repair: none
- temperature: 0.0
- seed: 42
- max output tokens: 512

Diagnostic NDCG@1/5/10/20 over these eight pilot sessions:
- NDCG@1: 0.000000
- NDCG@5: 0.123630
- NDCG@10: 0.236517
- NDCG@20: 0.313679

These pilot NDCG values are diagnostic only and are not the final PURE result.

## Important status-note

The handoff summary emitted `status = INCOMPLETE` even though all 8/8 sessions produced valid final rankings. This came from an overly specific pilot acceptance condition: the code required both historically known direct-ranking failure IDs to fail direct again in this particular rerun and therefore be counted as fallback recoveries.

That condition is not an invariant of the hybrid policy. In this execution:
- `A3RQZ1J5F5G104:10`, which had failed the earlier direct full run, produced a valid direct ranking this time and therefore correctly did not trigger fallback;
- `A26C4UAI3IXYF:6` failed direct structurally and was successfully recovered by the fresh rank-map fallback;
- both sessions that had failed standalone rank-map (`A2GSRMMRODQ4JH:4` and `A2GSRMMRODQ4JH:6`) succeeded through the direct-primary path.

Therefore the machine-reported `INCOMPLETE` label is a bookkeeping/acceptance-criterion mismatch, not a session-level experimental failure. The scientifically relevant hybrid invariant is: every session must end with a valid complete permutation, and every fallback that is actually triggered must itself pass the strict parser. The pilot satisfied that invariant 8/8.

The change in `A3RQZ1J5F5G104:10` between runs also shows that `temperature=0.0` plus `seed=42` on the local backend does not guarantee bit-for-bit identical generation across separate executions. This is why the final evaluation must report the actual protocol path used per session rather than assume that historical failures will recur identically.

## Decision

**Hybrid policy v4: ACCEPTED FOR CLEAN FULL-SCALE VALIDATION.**

This does not freeze Phase 5. A new all-94 run must be executed from scratch under the exact same hybrid policy. The final runner uses a corrected acceptance condition: PASS only when all 94 frozen sessions finish with valid rankings and there are zero session failures. Any structurally invalid direct result may trigger at most one fresh rank-map fallback; a failed fallback makes the session fail.

Final-run files:
- config: `config/phase5_pure_recommender_hybrid_full.toml`
- runner: `scripts/run_phase5_pure_recommender_hybrid_full.py`
- safe wrapper: `scripts/run_phase5_pure_recommender_hybrid_full_safe.py`
- output: `outputs/phase5_pure_recommender_hybrid_final_v4/`
