# Phase 5 PURE Recommender — Rank-map Pilot v3

## Status
**INCOMPLETE / standalone rank-map protocol rejected for final use**

## Purpose
Rank-map v3 was tested after the direct ranking-array protocol produced two malformed permutations in the first 94-session run and the score-based protocol produced excessive ties. The rank-map serialization asks the model to assign every numbered candidate an explicit integer rank position from 1 through 20. The strict parser accepts the response only when the rank values form an exact permutation of 1..20.

This is an explicit reproduction engineering choice. The paper defines the 20-candidate ranking task but does not publish the exact machine-readable output schema.

## Frozen inputs and runtime
- model: local derivative `llama-3.2-3b-instruct-uncensored`
- model alignment: not the exact paper checkpoint
- temperature: 0.0
- seed: 42
- max output tokens: 512
- Phase 1 frozen candidate sets unchanged
- Phase 4 frozen profile states unchanged
- target position `t` uses profile state `(user_id, t-1)`
- no future review or target marker is exposed
- no retry, tie-break, semantic repair, or structural repair

## Pilot coverage
The same eight diagnostic sessions used by scored pilot v2 were evaluated:
- the original six direct-ranking pilot sessions;
- the two sessions that failed the first full direct-ranking attempt.

## Result
- requested sessions: 8
- successful sessions: 6
- failed sessions: 2
- users represented among successful sessions: 4
- known direct-ranking failures tested: 2
- known direct-ranking failures successful under rank-map: 2/2
- prompt tokens on successful rows: 5,772 total; 962 mean; 1,666 max
- completion tokens on successful rows: 935 total; 155.833 mean
- latency on successful rows: 22.611 s total; 3.768 s mean
- diagnostic NDCG@1/5/10/20 on the six successful rows: 0.000000 / 0.354414 / 0.398940 / 0.430190
- overall status: INCOMPLETE

The diagnostic NDCG values are not final because two pilot sessions failed and therefore are excluded.

## Failed sessions
### `A2GSRMMRODQ4JH:4`
The model returned all 20 candidate keys, but rank value `16` was used twice and rank `19` was missing. The strict parser rejected the response.

### `A2GSRMMRODQ4JH:6`
The model returned all 20 candidate keys, but rank value `16` was used twice and rank `3` was missing. The strict parser rejected the response.

## Interpretation
The rank-map representation solved the two exact sessions that had failed the direct ranking-array protocol, but it introduced the same fundamental cross-item uniqueness problem on two different sessions. Replacing the ranking array with a candidate-to-rank object therefore does not eliminate the local backend/model's difficulty in emitting a globally unique 20-item ordering.

The standalone rank-map protocol is rejected for the final 94-session evaluation.

## Next protocol decision
The evidence from the two protocols is complementary:
- direct ranking succeeded on the ordinary pilot cases that rank-map failed;
- rank-map succeeded on both sessions that direct ranking failed.

The next experiment therefore tests one predefined **two-stage output policy**:
1. request the direct ranking-array output first;
2. accept it only if the strict parser validates a complete permutation;
3. if and only if the direct output is structurally invalid, discard it and issue a fresh rank-map request using the same frozen history, profile, candidates, model, temperature, seed, and token cap;
4. accept the fallback only if its strict parser validates a complete permutation;
5. never repair either response after generation.

This is a uniform conditional policy applied to every session, not manual patching of known failures. It must pass a pilot before any new 94-session evaluation is attempted.
