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

## Reproduction choice and validation evolution
The paper publishes the natural-language updater prompt but not its exact JSON schema or post-processing/deletion validator. This project therefore uses conservative engineering safeguards and labels them explicitly as reproduction choices.

The profile always remains grounded in accepted Review Extractor evidence. New unsupported preference text is never allowed into the downstream profile.

### Pilot v1 contract
The model returned exact same-category input strings. This prevented hallucinated new text, but the model still removed a unique non-conflicting entry simply while compacting the profile.

### Pilot v2 contract
The same exact-subset validator was retained and the prompt was strengthened to preserve unique evidence by default. Pilot v2 showed two remaining problems:
- arbitrary deletion of unrelated unique evidence still occurred;
- copying long evidence strings in the response caused a small rewrite, which the strict parser correctly rejected.

Detailed result: `docs/PHASE4_PROFILE_UPDATER_PILOT_V2.md`.

## Pilot v3 contract: ID selection + deterministic retention guard
Pilot v3 keeps the paper-derived LLM updater step but separates semantic selection from mechanical safety.

### Stable entry IDs
Each concatenated same-category entry receives a deterministic ID:
- likes: `L001`, `L002`, ...
- dislikes: `D001`, `D002`, ...
- key features: `K001`, `K002`, ...

The prompt still displays each ID together with the exact evidence string, but the structured response contains IDs only. The dynamic JSON schema limits each category to its own valid IDs. The parser rejects unknown IDs, cross-category IDs, duplicates, or malformed output.

This removes text-copy drift: the model can select evidence but cannot rewrite it.

### Deterministic retention guard
After the model selects IDs, every omitted unique string is checked mechanically. A model-requested deletion is permitted only when a retained same-category string has **clear lexical overlap** with the omitted string. The guard recognizes conservative cases such as:
- exact normalized duplicates;
- direct normalized string containment;
- strong token-set containment with sufficient shared content.

If no such retained witness exists, the omitted unique entry is restored automatically. Exact duplicate source strings collapse to one retained occurrence.

This means the final profile can remove obvious duplicate/overlap evidence, but prompt-only arbitrary deletion of unique evidence cannot propagate downstream.

The guard is intentionally conservative. It is not claimed to reproduce the paper's undisclosed conflict-resolution algorithm exactly. A direct semantic conflict that lacks enough lexical overlap will be preserved rather than silently deleted. This is preferable to unsupported information loss in the thesis-grade reproduction.

## Initialization
The profile begins empty. The first observed extraction is concatenated with this empty profile and passed through the same Profile Updater path as every later interaction. This keeps one uniform update rule instead of introducing a special first-step shortcut.

## Structured output in pilot v3
For each call, the response has the same three categories but contains valid entry IDs only, for example:

```json
{
  "likes": ["L001", "L003"],
  "dislikes": ["D002"],
  "key_features": ["K001", "K004"]
}
```

The runner records:
- previous profile;
- incoming frozen extraction;
- exact concatenated profile;
- raw model-selected profile after ID-to-text mapping;
- entries restored by the deterministic guard;
- deletions allowed by the guard;
- final updated profile;
- final removed entries and counts.

## Pilot history
### Pilot v1 — technical PASS, policy NOT accepted
- 3/3 successful updates;
- 0 technical failures;
- 1,424 total reported tokens;
- 2.840 s mean latency/update.

At update 2, `Arrived even faster than i expected.` was dropped despite being unique and not clearly redundant, overlapping, or conflicting. Therefore prompt-only deletion behavior was not accepted.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V1.md`.

### Pilot v2 — INCOMPLETE / policy NOT accepted
Configuration: 2 users × 4 chronological updates, with retention-biased instructions and the exact-subset output contract.

Observed result before fail-fast stop:
- 4 successful updates;
- 1 failed update;
- 2,626 tokens across successful updates;
- 2.856 s mean successful-update latency.

The first user still had unrelated unique evidence removed. The first update for the second user failed because the model shortened a key-feature string instead of copying it exactly. Therefore v2 was rejected.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V2.md`.

### Pilot v3 — configured
Pilot v3 keeps the same source, model, runtime, generation settings, and coverage as v2:
- deterministic 2 eligible users;
- first 4 chronological updates each;
- 8 expected updates total;
- initial profile empty per user;
- temperature 0.0;
- seed 42;
- max output tokens 1024;
- finalized runtime 512 / 256 / 1;
- output: `outputs/phase4_profile_updater_pilot_v3/`.

Acceptance requires all 8 updates to complete and the audit to show that final deletions are limited to mechanically defensible exact duplicate/clear-overlap cases after the retention guard.

## Relevant files
- `config/phase4_profile_updater_pilot.toml`
- `src/pure_recommender/pure/profile_updater.py`
- `src/pure_recommender/phase4/config.py`
- `scripts/run_phase4_profile_updater_pilot.py`
- `scripts/run_phase4_profile_updater_pilot_safe.py`
- `tests/test_profile_updater.py`
- `docs/PHASE4_PROFILE_UPDATER_PILOT_V1.md`
- `docs/PHASE4_PROFILE_UPDATER_PILOT_V2.md`

## Next after pilot
If pilot v3 is accepted, implement the full chronological Profile Updater state cache for all required user prefixes, freeze profile states, then implement the PURE recommender using the latest eligible profile for each of the 94 frozen recommendation sessions.
