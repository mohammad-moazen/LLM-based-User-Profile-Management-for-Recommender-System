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
- no paraphrasing, rewriting, new text, outside knowledge, or cross-category movement is allowed;
- duplicate output strings within a category are invalid;
- structural/schema violations or unsupported output strings fail the update rather than being silently repaired.

This is stricter than the unspecified paper implementation and is explicitly documented as a reproduction engineering choice.

## Retention-biased deletion policy
Pilot v1 showed that the original reproduction prompt still allowed arbitrary deletion of unique evidence. Pilot v2 therefore tightens the deletion rule while preserving the same subset validator:

- retain every unique entry by default;
- remove an entry only for an exact duplicate, clear redundancy/overlap, or clear direct conflict;
- never remove a unique non-overlapping, non-conflicting entry merely because it seems less relevant or because a shorter profile is preferred;
- for clear overlap, preserve the more specific/informative source string;
- for an unambiguous direct conflict, newer evidence may supersede older evidence because the concatenated category order is chronological;
- if conflict is uncertain, preserve both rather than silently deleting information;
- the updater still cannot rewrite or move evidence between categories.

The recency tie-break for an unambiguous conflict is a documented reproduction choice; the paper describes maintaining an up-to-date profile but does not publish an exact conflict-resolution algorithm.

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

## Pilot v1 — technical PASS, policy NOT accepted
Configuration:
- one deterministic eligible user;
- first 3 chronological updates;
- temperature 0.0;
- seed 42;
- max output tokens 1024;
- finalized runtime 512 / 256 / 1.

Result:
- 3/3 successful updates;
- 0 technical failures;
- 1,424 total reported tokens;
- 2.840 s mean latency/update.

However, at update 2 the updater dropped `Arrived even faster than i expected.` even though the string was unique and neither clearly redundant, overlapping, nor conflicting with the two newly added likes. That is over-compression beyond the intended paper operation. Therefore pilot v1 is **not accepted** as the final policy.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V1.md`.

## Pilot v2 — configured
Pilot v2 keeps the same frozen extractor source, model, generation settings, runtime, and exact-subset validator. It changes only the deletion instruction and expands qualitative coverage.

Configuration:
- deterministic selection of 2 users with at least 4 chronological extraction rows;
- first 4 updates per selected user;
- total expected updates: 8;
- initial profile: empty per user;
- temperature: 0.0;
- seed: 42;
- max output tokens: 1024;
- output: `outputs/phase4_profile_updater_pilot_v2/`.

The handoff now includes the exact `concatenated_profile`, `updated_profile`, and mechanically computed `removed_entries` for every category at every update. Pilot v2 is accepted only if all requested updates pass the strict subset validator **and** qualitative review confirms that removals are limited to defensible duplicate/overlap/conflict cases.

## Relevant files
- `config/phase4_profile_updater_pilot.toml`
- `src/pure_recommender/pure/profile_updater.py`
- `src/pure_recommender/phase4/config.py`
- `scripts/run_phase4_profile_updater_pilot.py`
- `scripts/run_phase4_profile_updater_pilot_safe.py`
- `tests/test_profile_updater.py`
- `docs/PHASE4_PROFILE_UPDATER_PILOT_V1.md`

## Next after pilot
If pilot v2 is accepted, implement the full chronological Profile Updater state cache for all required user prefixes, freeze profile states, then implement the PURE recommender using the latest eligible profile for each of the 94 frozen recommendation sessions.
