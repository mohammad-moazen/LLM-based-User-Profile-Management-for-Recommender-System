# Phase 4 PURE Profile Updater Protocol

## Purpose
This phase reproduces **STEP 2: Update User Profile** from PURE after the Review Extractor has been frozen. The updater maintains an evolving profile across chronological interactions and is validated before the final PURE recommender is implemented.

## Paper-derived behavior
Algorithm 1 concatenates the previous profile with the newly extracted representation independently for likes, dislikes, and key features. The Profile Updater then removes redundant/overlapping information and resolves conflicts to produce the new profile.

Published updater prompt template:

> You are given a list: {list}. Update this list by removing redundant or overlapping information. Note that crucial information should be preserved.

The paper does not publish the exact machine-readable schema, deletion validator, or conflict-resolution/post-processing implementation.

## Chronological/no-leakage policy
For interaction position `t`:
1. consume only the frozen Review Extractor output for review `t`;
2. concatenate it with profile `P_(t-1)`;
3. call Profile Updater to obtain `P_t`;
4. never include reviews or extractions from positions after `t`.

For a recommendation target at position `t+1`, only `P_t` is eligible. The target review is never visible before that target purchase.

## Frozen Review Extractor source
Only the homogeneous final artifact is allowed:

`outputs/phase3_review_extractor_final_1024/extractions.jsonl`

Historical extractor artifacts remain audit/development records and are not Phase 4 inputs.

## Reproduction safeguards
The profile must remain grounded in accepted Review Extractor evidence. The updater cannot introduce unsupported preference text.

### Stable same-category entry IDs
Each concatenated entry receives a deterministic category-scoped ID:
- likes: `L001`, `L002`, ...
- dislikes: `D001`, `D002`, ...
- key features: `K001`, `K002`, ...

The prompt displays the ID together with the exact evidence string, but the model returns IDs only. The dynamic JSON schema restricts each category to its own valid IDs. Unknown IDs, cross-category IDs, duplicate IDs, malformed structures, and invalid JSON are rejected.

This design prevents text-copy drift while preserving an LLM decision step.

## Accepted v4 information-preserving guard
Pilot v3 showed that symmetric lexical-overlap detection was not sufficient: the model could retain a shorter overlap and remove a richer sentence. The accepted v4 guard is directional.

For each same-category omitted entry:
1. exact duplicate source strings collapse to one occurrence;
2. an omitted unique string may be deleted only when a retained string has clear lexical overlap **and is strictly more informative**;
3. if no retained dominator exists, the omitted entry is restored;
4. after restoration, a deterministic second pass removes any shorter entry strictly dominated by another safe entry.

The dominance relation is conservative. A retained candidate must first pass the clear lexical-overlap rule and then either contain the omitted normalized phrase or have a strict content-token superset. Semantic conflict without sufficient lexical evidence is preserved rather than silently deleted.

This deterministic guard is an explicit project reproduction choice, not a claim about the paper's undisclosed implementation.

## Initialization
Each user profile begins empty. The first observed extraction is concatenated with the empty profile and passed through the same updater path as every later interaction.

## Pilot history
### Pilot v1 — technical PASS / policy rejected
- 3/3 successful updates
- 0 technical failures
- 1,424 reported tokens
- 2.840 s mean latency/update

The model removed a unique non-conflicting entry while compacting the profile. Prompt-only deletion was therefore not accepted.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V1.md`.

### Pilot v2 — INCOMPLETE / policy rejected
- 4 successful updates before fail-fast
- 1 failed update
- 2,626 reported tokens across successful updates
- 2.856 s mean successful-update latency

The model still removed unrelated unique evidence, and one response rewrote a key-feature string. The strict parser correctly rejected the rewrite.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V2.md`.

### Pilot v3 — technical PASS / policy not frozen
- 8/8 successful updates
- 0 failures
- 9 guard-restored entries
- 1 final removal
- 5,172 reported tokens
- 1.612 s mean latency/update

ID-only output removed the rewrite failure mode and the guard prevented arbitrary unique-evidence loss. However, the only final overlap removal kept the shorter sentence and deleted the richer sentence, revealing a directional information-loss problem.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V3.md`.

### Pilot v4 — PASS / accepted for full-scale validation
Coverage:
- 3 deterministic eligible users
- 5 chronological updates per user
- 15 expected updates

Observed:
- 15/15 successful updates
- 0 failures
- 51 guard-restored entries
- 1 final unique overlap removal
- 10,778 prompt tokens
- 1,003 completion tokens
- 11,781 total reported tokens
- 26.368 s total latency
- 1.758 s mean latency/update

The sole final removal was information-preserving: the shorter sentence `It has a lot of charm and it is challenging enough.` was removed while the richer sentence `Beautiful game. It has a lot of charm and it is challenging enough.` was retained.

No unrelated unique evidence survived as a deletion after the v4 guard. Pilot v4 is accepted as the policy for the full Phase 4 run.

Detailed record: `docs/PHASE4_PROFILE_UPDATER_PILOT_V4.md`.

## Full chronological state-cache run
The accepted policy is now applied to every successful frozen Phase 3 extraction, not merely a user sample.

Runner:
- `config/phase4_profile_updater_full.toml`
- `scripts/run_phase4_profile_updater_full.py`
- `scripts/run_phase4_profile_updater_full_safe.py`

Expected source workload:
- 20 users
- 134 chronological profile updates

The full runner validates that each user's extraction positions form a contiguous prefix `1..max_position`, then writes one safe state after every interaction to:

`outputs/phase4_profile_updater_final_v4/profile_states.jsonl`

The full summary records:
- successful/failed updates;
- prefix contiguity;
- guard restorations and allowed removals;
- reported token usage and maximum prompt token count;
- latency;
- diagnostic entry-count compaction versus exact-unique accumulated extractor evidence.

Entry-count compaction is only a diagnostic. The final recommender stage will measure actual recommendation prompt-token size, which is the closer analogue to the paper's token-efficiency analysis.

## Full-run acceptance criteria
Phase 4 is frozen only if:
1. all 134 expected updates succeed;
2. all user prefixes are contiguous and leakage-safe;
3. no malformed/unsupported model output enters a profile;
4. the finalized runtime remains stable;
5. prompt sizes remain viable under the fixed 8192 context setting;
6. the resulting state cache can map every frozen recommendation session to the profile immediately preceding its target.

Compression behavior is recorded rather than forced. If the conservative v4 guard yields negligible compaction at full scale, that limitation must be reported explicitly rather than weakening the safety rule silently.

## Relevant files
- `src/pure_recommender/pure/profile_updater.py`
- `src/pure_recommender/pure/profile_updater_guard_v4.py`
- `src/pure_recommender/phase4/config.py`
- `config/phase4_profile_updater_pilot.toml`
- `config/phase4_profile_updater_full.toml`
- `scripts/run_phase4_profile_updater_pilot.py`
- `scripts/run_phase4_profile_updater_pilot_v4_safe.py`
- `scripts/run_phase4_profile_updater_full.py`
- `scripts/run_phase4_profile_updater_full_safe.py`
- `tests/test_profile_updater.py`
- `docs/PHASE4_PROFILE_UPDATER_PILOT_V1.md`
- `docs/PHASE4_PROFILE_UPDATER_PILOT_V2.md`
- `docs/PHASE4_PROFILE_UPDATER_PILOT_V3.md`
- `docs/PHASE4_PROFILE_UPDATER_PILOT_V4.md`
