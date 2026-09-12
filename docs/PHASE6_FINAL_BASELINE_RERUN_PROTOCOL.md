# Phase 6 — Final Controlled Baseline Reruns

## Goal

Produce the thesis-grade comparison table only after PURE and all three purchased-item baselines are evaluated under the same frozen workload, finalized local runtime/generation settings, and the same mechanical output-validation policy.

Historical Phase 2 baseline scores remain preserved as historical artifacts. They are not overwritten and are not the final controlled comparison because they predate the output policy ultimately required by Phase 5.

## Frozen workload

All final comparison methods use:

- the same 20 selected users;
- the same 94 frozen continuous recommendation sessions;
- the same 20-item candidate set per session;
- the same candidate order generated in Phase 1;
- the same user-level NDCG aggregation policy;
- no target marker or future information.

## Final runtime/generation controls

- model: local derivative `llama-3.2-3b-instruct-uncensored`, GGUF Q8_0 (~3.84 GB)
- temperature: `0.0`
- generation seed: `42`
- max output tokens: `512`
- Context Length: `8192`
- Evaluation Batch: `512`
- Physical Batch: `256`
- Max Concurrent Predictions: `1`

These are local derivative-model results, not exact paper-checkpoint reproduction.

## Shared hybrid output policy

The recommendation method determines only the information/prompt semantics. The mechanical output policy is shared across PURE and every final baseline rerun:

1. Ask the model for a direct complete ranking of candidate numbers 1..20.
2. Use a structured JSON schema for the direct response.
3. Validate with the strict complete-permutation parser.
4. Only when that direct model output is structurally invalid, discard it and issue one fresh rank-map request for the same recommendation method and same visible inputs.
5. Do not show the malformed direct response to the fallback call.
6. Permit at most one fallback request.
7. Require the fallback rank map to contain every candidate key and an exact permutation of ranks 1..20.
8. Perform no post-generation candidate insertion, deletion, inference, reordering, score tie-break, or repair.
9. API/network failures or unrelated data-validation failures do not silently trigger the serialization fallback.

The PURE paper does not publish an exact machine-readable output schema. This shared hybrid policy is therefore an explicit reproduction engineering choice applied uniformly for final comparison fairness.

## Method-specific information remains unchanged

### Sequential
Only chronological purchased-item titles and frozen candidate titles are visible. No reviews, ratings, profile, recency marker beyond chronology, or demonstration framing are added.

### Recency-Focused
Same purchased-item and candidate information as Sequential, plus the paper-aligned explicit emphasis on the most recent purchase.

### ICL
Earlier purchases through `t-2` are shown as context and the purchase at `t-1` is shown as the in-context demonstrated outcome, followed by the current frozen candidate set.

### PURE
Uses the frozen Phase 4 profile state at `t-1`, chronological purchased items, and the same frozen candidate set.

## Execution order

Run the baselines one at a time so each result can be inspected and frozen before moving to the next method:

1. Sequential — `phase6_sequential_hybrid_full_v1`
2. Recency-Focused — prepared after Sequential is reviewed
3. ICL — prepared after Recency-Focused is reviewed
4. Final comparison table — frozen only after all three baseline reruns pass 94/94

## Sequential final rerun

Files:

- config: `config/phase6_sequential_hybrid.toml`
- runner: `scripts/run_phase6_sequential_hybrid.py`
- safe wrapper: `scripts/run_phase6_sequential_hybrid_safe.py`
- rank-map fallback prompt: `src/pure_recommender/baselines/sequential_rankmap.py`
- output: `outputs/phase6_sequential_hybrid_final_v1/`

Acceptance criteria:

- exactly 94 frozen sessions attempted;
- 94/94 sessions finish with a valid complete ranking;
- zero session failures;
- any direct structural failure may trigger at most one fresh Sequential rank-map fallback;
- every triggered fallback must pass strict validation;
- no post-generation repair is used;
- summary records NDCG@1/5/10/20, protocol path counts, token usage, and latency.
