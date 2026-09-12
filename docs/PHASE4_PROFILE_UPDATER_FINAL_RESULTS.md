# Phase 4 Profile Updater — Final Full v4 Results

## Status
**PASS / FROZEN**

The accepted v4 Profile Updater policy was executed from scratch over every review-extraction prefix required by the frozen continuous recommendation sessions. The run consumes only the homogeneous final Phase 3 Review Extractor artifact and writes one leakage-safe profile state after each observed interaction.

Official downstream artifact:

`outputs/phase4_profile_updater_final_v4/profile_states.jsonl`

## Final run
- users: **20**
- expected updates: **134**
- successful updates: **134**
- failed updates: **0**
- prefix contiguity invariant: **PASS**
- temperature: **0.0**
- seed: **42**
- max output tokens: **1024**
- structured output: dynamic same-category entry-ID schema
- validation: same-category ID selection plus information-preserving dominance guard

## Guard behavior
Across all chronological updates:
- entries omitted by the model but restored by the deterministic guard: **619**
- final allowed removals: **11**

The high restoration count is expected under the conservative thesis-grade policy. The LLM is allowed to propose compaction, but unsupported deletion of unique evidence cannot propagate into the final profile. Final removal is limited to exact duplicate evidence or lexical overlaps for which another same-category entry is strictly more informative.

## Entry-count compaction diagnostics
Across all prefixes:
- cumulative raw unique prefix entries: **2,925**
- cumulative safe prefix entries: **2,849**
- cumulative entry-count compaction: **2.598%**

Across final per-user profile states:
- final raw unique entries: **472**
- final safe entries: **461**
- final entry-count compaction: **2.331%**

These entry-count ratios are diagnostic only. The relevant token footprint of the final recommendation prompt is measured separately in Phase 5.

## Runtime and token usage
- prompt tokens: **146,320**
- completion tokens: **15,137**
- total reported tokens: **161,457**
- maximum single updater prompt: **4,287 tokens**
- maximum-prompt task: `A3RQZ1J5F5G104:19`
- total latency: **408.766 s** (~6.81 min)
- mean latency/update: **3.050 s**
- median latency/update: **1.728 s**

The maximum measured updater prompt remained well below the finalized 8,192-token local context setting.

## Frozen policy
The Phase 4 profile is initialized empty and updated chronologically. For each observed review extraction:
1. concatenate the previous safe profile and the new accepted Phase 3 evidence;
2. assign stable same-category IDs;
3. ask the LLM to retain the IDs that should remain;
4. map IDs back to the exact source evidence;
5. apply the deterministic information-preserving dominance guard;
6. persist the resulting safe profile state.

The updater never creates new profile text. This ID interface and deterministic guard are explicit reproduction engineering choices because the paper does not publish an exact updater JSON schema or post-processing algorithm.

## Leakage invariant for Phase 5
For a frozen recommendation target at purchase position `t`, the recommender may use only the profile state after interaction position `t-1`. The target review is not observable before predicting that target.

## Scientific labeling
This is a local derivative-model reproduction artifact generated with `llama-3.2-3b-instruct-uncensored`, not the exact paper checkpoint. The preprocessing, prompt serialization, JSON schema, and deterministic safety guard are documented reproduction choices.
