"""Small Git-based handoff channel for local experiment results.

The project is developed collaboratively: code/documentation changes are pushed
from ChatGPT, while expensive LLM experiments run on the user's Windows machine.
This module lets a local runner publish one compact machine-readable handoff file
without staging or committing unrelated local work (especially README changes).

The handoff is intentionally a *summary channel*, not a replacement for the full
local experiment artifacts under ``outputs/``. The file is overwritten on every
run. Because Git retains commit history, secrets and private credentials must
never be written to the handoff payload.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Mapping


HANDOFF_RELATIVE_PATH = Path("handoff/latest.json")


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_handoff(
    repo_root: Path,
    payload: Mapping[str, object],
    *,
    relative_path: Path = HANDOFF_RELATIVE_PATH,
) -> Path:
    """Overwrite the tracked handoff JSON with a compact experiment payload."""

    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def publish_handoff(
    repo_root: Path,
    payload: Mapping[str, object],
    *,
    commit_message: str,
    auto_push: bool = True,
    relative_path: Path = HANDOFF_RELATIVE_PATH,
) -> tuple[bool, str]:
    """Write, commit only the handoff path, and optionally push it.

    Important safety properties:
    - only ``handoff/latest.json`` is explicitly added;
    - ``git commit --only`` prevents unrelated staged/local changes from entering
      the handoff commit;
    - the function never performs an automatic pull/rebase/merge;
    - a publication failure never edits or discards unrelated working-tree files.

    Returns ``(success, message)``. Experiment runners should treat publication
    failure as a reporting problem, not as an experiment-result failure.
    """

    path = write_handoff(repo_root, payload, relative_path=relative_path)
    relative = path.relative_to(repo_root).as_posix()

    inside = _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return False, "repository is not a Git working tree; handoff written locally only"

    branch_result = _run_git(repo_root, ["branch", "--show-current"])
    branch = branch_result.stdout.strip()
    if branch_result.returncode != 0 or not branch:
        return False, "could not determine current Git branch; handoff written locally only"

    add_result = _run_git(repo_root, ["add", "--", relative])
    if add_result.returncode != 0:
        return False, f"git add failed: {add_result.stderr.strip()}"

    staged_result = _run_git(repo_root, ["diff", "--cached", "--quiet", "--", relative])
    if staged_result.returncode == 0:
        # Nothing changed relative to HEAD; there is nothing new to publish.
        return True, f"handoff unchanged on branch {branch}; no commit needed"
    if staged_result.returncode != 1:
        return False, f"could not inspect staged handoff: {staged_result.stderr.strip()}"

    commit_result = _run_git(
        repo_root,
        ["commit", "--only", "-m", commit_message, "--", relative],
    )
    if commit_result.returncode != 0:
        return False, f"handoff commit failed: {commit_result.stderr.strip()}"

    if not auto_push:
        return True, f"handoff committed locally on {branch}; auto-push disabled"

    push_result = _run_git(repo_root, ["push", "origin", f"HEAD:{branch}"])
    if push_result.returncode != 0:
        return False, (
            "handoff committed locally but push failed; do not auto-pull/rebase. "
            f"Git said: {push_result.stderr.strip()}"
        )

    return True, f"handoff committed and pushed to origin/{branch}"
