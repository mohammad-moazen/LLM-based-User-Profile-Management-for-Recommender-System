"""Run the accepted PURE recommender on all frozen sessions.

This wrapper reuses the pilot runner as the single execution engine so prompt
construction, profile/session alignment, structured output, ranking parsing, and
NDCG aggregation cannot drift between pilot and full evaluation. Only the config,
experiment identity, output directory, and handoff compactness differ.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import traceback

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.phase5 import load_phase5_config
import run_phase5_pure_recommender as shared_runner


EXPERIMENT = "phase5_pure_recommender_full"
CONFIG_PATH = REPO_ROOT / "config" / "phase5_pure_recommender_full.toml"
RUN_VERSION = "full_v1"


def _publish_full(payload: dict[str, object], status_word: str) -> None:
    """Publish a compact full-run mailbox instead of all 94 successful rows."""

    payload["experiment"] = EXPERIMENT
    summary = payload.get("summary")
    if isinstance(summary, dict):
        summary["run_version"] = RUN_VERSION

    rows = payload.get("rows")
    if isinstance(rows, list):
        payload["rows"] = [
            row
            for row in rows
            if isinstance(row, dict) and row.get("status") != "ok"
        ]

    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: phase5 PURE recommender full {status_word.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def _rewrite_local_summary() -> None:
    """Make the local full-run summary self-identify as the final evaluation."""

    config = load_phase5_config(CONFIG_PATH)
    summary_path = config.output.directory / "summary.json"
    if not summary_path.exists():
        return
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    payload["run_version"] = RUN_VERSION
    payload["experiment"] = EXPERIMENT
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    # Keep the shared engine but give the full run its own identity and mailbox.
    shared_runner.EXPERIMENT = EXPERIMENT
    shared_runner._publish = _publish_full

    original_argv = sys.argv[:]
    try:
        # The shared runner uses argparse. Inject the full config only when the
        # caller did not explicitly provide one.
        if "--config" not in sys.argv:
            sys.argv.extend(["--config", str(CONFIG_PATH)])
        result = shared_runner.main()
        _rewrite_local_summary()
        return result
    except Exception as exc:
        payload: dict[str, object] = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc(),
        }
        ok, message = publish_handoff(
            REPO_ROOT,
            payload,
            commit_message="handoff: phase5 PURE recommender full traceback",
            auto_push=True,
        )
        print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
        raise
    finally:
        sys.argv[:] = original_argv


if __name__ == "__main__":
    raise SystemExit(main())
