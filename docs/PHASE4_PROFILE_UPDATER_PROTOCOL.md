# Phase 4 PURE Profile Updater Protocol

## Purpose
This phase reproduces **STEP 2: Update User Profile** from PURE after the Review Extractor has been frozen. The updater maintains a compact evolving profile across chronological interactions and is validated before the final PURE recommender is implemented.

## Paper-derived behavior
Algorithm 1 first concatenates the previous profile with the newly extracted representation independently for likes, dislikes, and key features. The Profile Updater then removes redundancy and conflicts to produce the new profile.

Published updater prompt template:

> You are given a list: {list}. Update this list by removing redundant or overlapping information. Note that crucial information should be preserved.

The paper also states that the updater refines newly extracted representations by eliminating redundancies and resolving conflicts with the existing profile so the profile remains compact and coherent.

## Chronological/no-leakage policy
For interaction position `t`:
1. consume only the frozen Review Extractor output for review `t`;
2. concatenate it with profile `P_(t-1)`;
3. call Profile Updater to obtain `P_t`;
4. never include reviews or extractions from positions after `t`.

For a recommendation target at position `t+1`, only `P_t` is eligible. The target review is never visible before that target purchase.

## Final Review Extractor source
Only the homogeneous final artifact is allowed:

`outputs/phase3_review_extractor_final_1024/extractions.jsonl`

The historical v5 artifact and the 133/134 clean attempt are retained for audit but are not downstream inputs.

## Reproduction choice: subset-preserving updater
The paper publishes the natural-language prompt but not an exact JSON schema or validation strategy. To prevent the Profile Updater from introducing unsupported new preference text, this project uses a conservative subset contract:

- input is the concatenation of previous profile strings and the new accepted Review Extractor evidence strings;
- output has exactly three arrays: `likes`, `dislikes`, `key_features`;
- every output string must be copied exactly from the same corresponding input category;
- entries may be removed to eliminate redundancy, overlap, or conflicts;
- no paraphrasing, rewriting, new text, outside knowledge, or cross-category movement is allowed;
- duplicate output strings within a category are invalid;
- structural/schema violations or unsupported output strings fail the update rather than being silently repaired.

This is stricter than the unspecified paper implementation and is explicitly documented as a reproduction engineering choice.

## Initialization
The profile begins empty. The first observed extraction is concatenated with this empty profile and passed through the same Profile Updater path as every later interaction. This keeps one uniform update rule instead of introducing a special first-step shortcut.

## Structured output
The updater requests a strict JSON schema:

```json
{
  "likes": ["exact input string", "..."],
  "dislikes": ["exact input string", "..."],
  "key_features": ["exact input string", "..."]
}
```

The deterministic parser validates exact same-category subset membership.

## Pilot v1
Pilot configuration:
- source: clean homogeneous final Review Extractor artifact;
- deterministic user selection: lexicographically first user with at least 3 extraction rows;
- chronological updates: first 3 extraction rows for that user;
- initial profile: empty;
- temperature: 0.0;
- seed: 42;
- max output tokens: 1024;
- model: local derivative `llama-3.2-3b-instruct-uncensored`;
- finalized LM Studio runtime: Evaluation Batch 512 / Physical Batch 256 / Max Concurrent 1.

The pilot handoff includes the previous profile, incoming extraction, updated profile, counts removed from the concatenated profile, latency, and any error/raw response. The pilot is accepted only if all requested updates parse successfully and pass the subset validator, followed by qualitative review of whether crucial information is being preserved sensibly.

## Relevant files
- `config/phase4_profile_updater_pilot.toml`
- `src/pure_recommender/pure/profile_updater.py`
- `src/pure_recommender/phase4/config.py`
- `scripts/run_phase4_profile_updater_pilot.py`
- `scripts/run_phase4_profile_updater_pilot_safe.py`
- `tests/test_profile_updater.py`

## Next after pilot
If pilot v1 is accepted, implement the full chronological Profile Updater state cache for all required user prefixes, freeze profile states, then implement the PURE recommender using the latest eligible profile for each of the 94 frozen recommendation sessions.
