# Phase 2 Recency-Focused Results

## Status
**PASS / FROZEN** for the 20-user / 94-session Video Games pilot using the active local derivative model.

## Experimental basis
- Dataset: Amazon Review Data 2018 / Video Games 5-core
- Frozen users: 20
- Frozen recommendation sessions: 94
- Candidate size: 20 (1 ground-truth + 19 non-interacted negatives)
- Candidate sets: identical to the frozen Sequential baseline
- Model: `llama-3.2-3b-instruct-uncensored`
- Model label: local derivative-model result; not exact paper-checkpoint reproduction
- Temperature: 0.0
- Maximum output tokens: 512
- Generation seed: 42
- Aggregation: average NDCG across sessions within each user first, then average across users

## Final full-run result
- Successful sessions: 94
- Failed sessions: 0
- Users: 20
- NDCG@1: **0.078333**
- NDCG@5: **0.199726**
- NDCG@10: **0.239947**
- NDCG@20: **0.378652**
- Total reported tokens: **64,677**
- Mean latency: **1.394 seconds/session**
- Status: **PASS**

## Comparison with the frozen Sequential baseline
Sequential result:
- NDCG@1: 0.061667
- NDCG@5: 0.182577
- NDCG@10: 0.227799
- NDCG@20: 0.366378
- Total reported tokens: 60,669
- Mean latency: 1.385 seconds/session

Recency-Focused minus Sequential:
- NDCG@1: **+0.016666** (~+27.03% relative)
- NDCG@5: **+0.017149** (~+9.39% relative)
- NDCG@10: **+0.012148** (~+5.33% relative)
- NDCG@20: **+0.012274** (~+3.35% relative)
- Total reported tokens: **+4,008** (~+6.61%)
- Mean latency: **+0.009 s/session** (~+0.65%)

The full pilot therefore shows a consistent NDCG improvement at all four cutoffs when the prompt explicitly emphasizes the most recent purchase. This is an observation about the current local derivative-model experiment and should not be generalized beyond this frozen pilot without additional runs.

## Protocol note
The only recommendation-behavior difference from Sequential is explicit emphasis on the purchase at time step `t-1`. The validated numbered-candidate output interface remains unchanged:
- history uses product titles only;
- candidates are numbered product titles;
- the model ranks candidate numbers;
- the runner maps numbers back to the unchanged frozen ASIN list;
- malformed rankings are rejected rather than repaired.

See `docs/PHASE2_RECENCY_PROTOCOL.md` for the complete protocol.

## Freeze decision
The Recency-Focused baseline is frozen for this pilot because:
- all 94 frozen sessions produced valid complete rankings;
- no session was excluded;
- the exact same frozen users, candidate sets, target items, metric code, model, and generation settings as Sequential were retained;
- the only intended behavioral change was the paper-derived recency instruction.

Next baseline: **In-Context Learning (ICL)**.
