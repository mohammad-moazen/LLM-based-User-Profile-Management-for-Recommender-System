"""Run the Phase 2 LLM Sequential baseline on frozen Phase 1 sessions.

The PURE paper's Sequential baseline uses only chronological purchased-item
interactions and the candidate list. This runner therefore deliberately excludes
reviews, ratings, PURE profiles, and any ground-truth marker from the LLM prompt.

Initial checked-in configuration runs only three real sessions. After prompt and
parser behavior are inspected locally, set ``max_sessions = 0`` in
``config/phase2.toml`` to evaluate all 94 frozen pilot sessions.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.baselines import (
    build_sequential_messages,
    parse_complete_ranking,
    target_rank,
)
from pure_recommender.evaluation.metrics import aggregate_user_ndcg, ndcg_at_ks_from_rank
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase2 import (
    load_histories,
    load_items,
    load_phase2_config,
    load_sessions,
)


def _load_latest_results(path: Path) -> dict[str, dict[str, object]]:
    """Return the latest appended record for every session id."""

    latest: dict[str, dict[str, object]] = {}
    if not path.exists():
        return latest
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if isinstance(row, dict) and isinstance(row.get("session_id"), str):
                latest[row["session_id"]] = row
    return latest


def _append_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _validate_frozen_session(
    session: dict[str, object],
    histories: dict[str, list[dict[str, object]]],
    item_titles: dict[str, str],
) -> tuple[list[dict[str, object]], list[str], str]:
    """Validate and return observed history, candidates, and target ASIN."""

    user_id = str(session["user_id"])
    target_position = int(session["target_position"])
    target_asin = str(session["target_asin"])
    candidate_asins = [str(value) for value in session["candidate_asins"]]

    if user_id not in histories:
        raise ValueError(f"Session user {user_id!r} not found in canonical interactions")
    history = histories[user_id]
    target_index = target_position - 1
    if target_index < 1 or target_index >= len(history):
        raise ValueError(f"Invalid target position for session {session['session_id']!r}")

    canonical_target = str(history[target_index]["asin"])
    if canonical_target != target_asin:
        raise ValueError(
            f"Frozen session target mismatch: session={target_asin}, history={canonical_target}"
        )
    if target_asin not in candidate_asins:
        raise ValueError("Ground-truth item is absent from frozen candidate list")
    if len(set(candidate_asins)) != len(candidate_asins):
        raise ValueError("Frozen candidate list contains duplicates")
    missing_titles = [asin for asin in candidate_asins if asin not in item_titles]
    if missing_titles:
        raise ValueError(f"Candidate ASINs missing canonical titles: {missing_titles}")

    # Only interactions strictly before the target are visible to the model.
    observed_history = history[:target_index]
    return observed_history, candidate_asins, target_asin


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PURE Phase 2 Sequential baseline")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase2.toml"),
        help="Path to Phase 2 TOML config",
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
        help="Path to local LLM TOML config",
    )
    args = parser.parse_args()

    config = load_phase2_config(args.config)
    llm_config = load_local_llm_config(args.llm_config)

    for label, path in (
        ("items", config.input.items_path),
        ("interactions", config.input.interactions_path),
        ("sessions", config.input.sessions_path),
    ):
        if not path.exists():
            raise FileNotFoundError(f"Frozen Phase 1 {label} artifact not found: {path}")

    print("Loading frozen Phase 1 artifacts...")
    item_titles = load_items(config.input.items_path)
    histories = load_histories(config.input.interactions_path)
    all_sessions = load_sessions(config.input.sessions_path)
    sessions = (
        all_sessions
        if config.experiment.max_sessions == 0
        else all_sessions[: config.experiment.max_sessions]
    )

    client = OpenAICompatibleLLMClient(
        base_url=llm_config.base_url,
        timeout_seconds=llm_config.timeout_seconds,
    )
    visible_models = client.list_models()
    if llm_config.model not in visible_models:
        raise RuntimeError(
            f"Configured model {llm_config.model!r} is not exposed by the local server. "
            f"Visible models: {visible_models}"
        )

    output_dir = config.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.jsonl"
    summary_path = output_dir / "summary.json"

    latest_results = _load_latest_results(results_path) if config.experiment.resume else {}
    completed_ok = {
        session_id
        for session_id, row in latest_results.items()
        if row.get("status") == "ok"
    }

    print("\n" + "=" * 88)
    print("PURE PHASE 2 — SEQUENTIAL BASELINE")
    print("=" * 88)
    print(f"Model              : {llm_config.model}")
    print(f"Endpoint           : {llm_config.base_url}")
    print(f"Frozen sessions    : {len(all_sessions)}")
    print(f"Requested this run : {len(sessions)}")
    print(f"Temperature        : {config.generation.temperature}")
    print(f"Max output tokens  : {config.generation.max_tokens}")
    print(f"Generation seed    : {config.generation.seed}")
    print(f"Resume             : {config.experiment.resume}")
    if "uncensored" in llm_config.model.lower():
        print("Model alignment     : derivative local model; results are NOT exact paper-model reproduction")

    for ordinal, session in enumerate(sessions, start=1):
        session_id = str(session["session_id"])
        if session_id in completed_ok:
            print(f"[{ordinal:03d}/{len(sessions):03d}] {session_id}: already complete; skipping")
            continue

        observed_history, candidate_asins, target_asin = _validate_frozen_session(
            session,
            histories,
            item_titles,
        )
        messages = build_sequential_messages(
            history=observed_history,
            candidate_asins=candidate_asins,
            item_titles=item_titles,
        )

        print(
            f"[{ordinal:03d}/{len(sessions):03d}] {session_id}: "
            f"history={len(observed_history)}, candidates={len(candidate_asins)} ...",
            flush=True,
        )
        started = time.perf_counter()
        raw_content = ""
        try:
            response = client.chat_completion(
                model=llm_config.model,
                messages=messages,
                temperature=config.generation.temperature,
                max_tokens=config.generation.max_tokens,
                seed=config.generation.seed,
            )
            elapsed = time.perf_counter() - started
            raw_content = response.content
            ranking = parse_complete_ranking(raw_content, candidate_asins)
            rank = target_rank(ranking, target_asin)
            ndcg = ndcg_at_ks_from_rank(rank)

            result: dict[str, object] = {
                "session_id": session_id,
                "user_id": str(session["user_id"]),
                "target_position": int(session["target_position"]),
                "target_asin": target_asin,
                "status": "ok",
                "model": llm_config.model,
                "ranking": ranking,
                "target_rank": rank,
                "ndcg": {str(k): value for k, value in ndcg.items()},
                "latency_seconds": elapsed,
                "usage": dict(response.usage) if response.usage else None,
                "raw_response": raw_content,
            }
            _append_result(results_path, result)
            latest_results[session_id] = result
            completed_ok.add(session_id)
            print(f"    target rank={rank}; latency={elapsed:.2f}s")
        except Exception as exc:
            elapsed = time.perf_counter() - started
            error_result: dict[str, object] = {
                "session_id": session_id,
                "user_id": str(session["user_id"]),
                "target_position": int(session["target_position"]),
                "target_asin": target_asin,
                "status": "error",
                "model": llm_config.model,
                "latency_seconds": elapsed,
                "error": str(exc),
                "raw_response": raw_content,
            }
            _append_result(results_path, error_result)
            latest_results[session_id] = error_result
            print(f"    ERROR: {exc}")
            if config.experiment.fail_fast:
                raise

    requested_ids = [str(session["session_id"]) for session in sessions]
    requested_results = [latest_results[session_id] for session_id in requested_ids if session_id in latest_results]
    ok_results = [row for row in requested_results if row.get("status") == "ok"]
    error_results = [row for row in requested_results if row.get("status") != "ok"]

    ranks_by_user: dict[str, list[int]] = defaultdict(list)
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    latencies: list[float] = []
    for row in ok_results:
        ranks_by_user[str(row["user_id"])].append(int(row["target_rank"]))
        latencies.append(float(row["latency_seconds"]))
        usage = row.get("usage")
        if isinstance(usage, dict):
            total_prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
            total_completion_tokens += int(usage.get("completion_tokens", 0) or 0)
            total_tokens += int(usage.get("total_tokens", 0) or 0)

    metrics = aggregate_user_ndcg(ranks_by_user) if ranks_by_user else {1: 0.0, 5: 0.0, 10: 0.0, 20: 0.0}
    summary: dict[str, object] = {
        "baseline": "Sequential",
        "model": llm_config.model,
        "model_alignment": (
            "derivative_local_model_not_exact_paper_checkpoint"
            if "uncensored" in llm_config.model.lower()
            else "model_identifier_does_not_independently_prove_checkpoint_identity"
        ),
        "frozen_phase1_sessions": len(all_sessions),
        "requested_sessions": len(sessions),
        "successful_sessions": len(ok_results),
        "failed_sessions": len(error_results),
        "users_in_successful_sessions": len(ranks_by_user),
        "generation": {
            "temperature": config.generation.temperature,
            "max_tokens": config.generation.max_tokens,
            "seed": config.generation.seed,
        },
        "ndcg": {str(k): value for k, value in metrics.items()},
        "usage_totals": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
        },
        "latency": {
            "total_seconds": sum(latencies),
            "mean_seconds": (sum(latencies) / len(latencies) if latencies else 0.0),
        },
        "status": "PASS" if len(ok_results) == len(sessions) and not error_results else "INCOMPLETE",
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    print("\n" + "=" * 88)
    print("PHASE 2 SEQUENTIAL SUMMARY")
    print("=" * 88)
    print(f"successful_sessions : {len(ok_results)}")
    print(f"failed_sessions     : {len(error_results)}")
    print(f"users               : {len(ranks_by_user)}")
    for k in (1, 5, 10, 20):
        print(f"NDCG@{k:<2}             : {metrics[k]:.6f}")
    print(f"total_tokens        : {total_tokens}")
    print(f"mean_latency_sec    : {summary['latency']['mean_seconds']:.3f}")
    print(f"status              : {summary['status']}")
    print(f"results             : {results_path}")
    print(f"summary             : {summary_path}")

    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
