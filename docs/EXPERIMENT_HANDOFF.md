# Automatic Experiment Handoff

## Purpose
Local LLM experiments run on the user's Windows machine, while code and documentation are maintained through the shared GitHub branch. To avoid manually copying long terminal outputs into chat, the project uses one compact tracked handoff file:

`handoff/latest.json`

A local experiment runner may overwrite this file, commit **only this path**, and push it to the current branch. ChatGPT can then read the handoff from GitHub, transfer durable facts into the appropriate protocol/result/project-state documents, and reset the handoff file to a small READY payload in a later push.

## Why the file is overwritten instead of deleted
Deleting and recreating the file adds unnecessary branch churn and does not make previously committed content disappear from Git history. A stable path is easier to automate and less conflict-prone.

The handoff therefore behaves as a mailbox:

1. `READY` — no unprocessed experiment result.
2. Local runner overwrites it with `RESULT` or `ERROR` data and pushes one narrow commit.
3. ChatGPT reads it and records important durable information elsewhere.
4. ChatGPT resets the same file to `READY` in a subsequent repository update.

## Git safety
The publisher is implemented in:

`src/pure_recommender/experiment_handoff.py`

Its Git behavior is intentionally conservative:

- only `handoff/latest.json` is explicitly added;
- `git commit --only` is used so unrelated staged/local changes are not included;
- it never performs automatic pull, merge, rebase, stash, or checkout operations;
- it never touches README or other unrelated working-tree files;
- if the remote branch has advanced, push failure is reported and the experiment result remains available locally;
- experiment success/failure is independent from handoff publication success/failure.

This is important because the user's local README may contain uncommitted work.

## Privacy / history warning
Although the handoff is called temporary, Git commit history is persistent. Deleting or resetting the file later does **not** guarantee that previous contents disappear from repository history.

Therefore the handoff must never contain:

- passwords, access tokens, API keys, private credentials;
- private personal information;
- model files or large raw datasets;
- full experiment artifacts that already live under ignored `outputs/` directories.

It should contain only compact summaries, parser/runtime errors, selected raw model responses needed for debugging, and very small source snippets when qualitative inspection genuinely requires them.

## Manual fallback
If automatic push fails, the runner prints a handoff publication warning. Do not let the runner auto-pull or auto-rebase around that failure. First synchronize the branch normally, then republish or send the compact output manually.

## Current integration
Phase 3 Review Extractor uses this handoff channel for both successful pilot/full-run summaries and fail-fast parser/grounding errors. Future experiment runners should reuse the same helper rather than creating new ad-hoc result files.
