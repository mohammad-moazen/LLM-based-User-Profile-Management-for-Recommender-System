# Phase 5 Malformed-Ranking Corrective-Retry Diagnostic

## Purpose
The first full PURE recommender attempt completed 92/94 sessions. Two model responses were valid JSON arrays of length 20 but were not complete permutations: candidate number 20 was duplicated and one other candidate number was omitted. The strict parser correctly rejected both rows.

The diagnostic tested whether one formatting-only corrective retry could recover those rows without deterministic post-generation repair.

## Protocol
The retry preserved the same:
- frozen session history;
- frozen Phase 4 profile state;
- frozen candidate set and order;
- local derivative model;
- temperature 0.0;
- seed 42;
- max output tokens 512;
- complete-numbered-ranking JSON schema.

The previous invalid model response was appended to the conversation and the model was asked only to return a complete unique permutation of candidate numbers 1..20.

No candidate was inserted, deleted, inferred, or reordered by deterministic code.

## Result
- failed rows tested: 2
- successful corrective retries: 0
- failed corrective retries: 2
- status: INCOMPLETE / retry policy rejected

### `A26C4UAI3IXYF:6`
First attempt:
- duplicate: 20
- missing: 19

Corrective retry reproduced the same malformed ranking, including duplicate 20 and omitted 19.

### `A3RQZ1J5F5G104:10`
First attempt:
- duplicate: 20
- missing: 13

Corrective retry reproduced the same malformed ranking, including duplicate 20 and omitted 13.

## Interpretation
At temperature 0.0 with seed 42, the formatting-only retry is deterministic for these two prompts and does not escape the malformed direct-permutation output. Repeating the same retry policy would therefore not provide a scientifically meaningful recovery mechanism.

The local serving backend also did not enforce the requested JSON Schema `uniqueItems` property strongly enough to prevent these arrays. The project therefore rejects both silent repair and repeated same-protocol retries.

## Next protocol experiment
A scored-output serialization is introduced as an explicit reproduction engineering choice. The recommendation task is unchanged: rank the same 20 frozen candidates by next-purchase likelihood. Instead of emitting a permutation directly, the model must emit one required integer likelihood score for every candidate number. Ranking is then obtained deterministically by descending model score; exact score ties are broken by frozen candidate number ascending.

This avoids the unsupported cross-array uniqueness constraint while still requiring model output for every candidate. It does not change the frozen history, profile, candidates, model, temperature, seed, or recommendation objective.

Before any new 94-session evaluation, the scored protocol is tested on eight sessions: the original six successful pilot sessions plus both malformed full-run sessions.
