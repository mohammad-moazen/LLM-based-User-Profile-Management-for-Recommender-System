"""Run the PURE STEP 3 recommender on frozen sessions and frozen profile states."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.baselines import parse_complete_ranking, target_rank
from pure_recommender.evaluation.metrics import aggregate_user_ndcg, ndcg_at_ks_from_rank
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase2 import load_histories, load_items, load_sessions
from pure_recommender.phase5 import load_phase5_config
from pure_recommender.pure import (
    build_pure_recommender_messages,
    profile_from_mapping,
    pure_recommender_response_format,
)


EXPERIMENT = "phase5_pure_recommender_pilot"


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _load_profile_states(path: Path) -> dict[tuple[str, int], dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Frozen Phase 4 profile-state artifact not found: {path}")

    latest: dict[tuple[str, int], dict[str, object]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            user_id = str(row.get("user_id", "")).strip()
            try:
                position = int(row.get("interaction_position"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid interaction_position at {path}:{line_number}") from exc
            if not user_id or position < 1:
                raise ValueError(f"Invalid profile-state identity at {path}:{line_number}")
            latest[(user_id, position)] = row

    bad = [key for key, row in latest.items() if row.get("status") != "ok"]
    if bad:
        raise RuntimeError(f"Profile-state artifact contains non-successful latest rows: {bad[:10]}")
    return latest


def _validate_session(
    session: dict[str, object],
    histories: dict[str, list[dict[str, object]]],
    item_titles: dict[str, str],
    profile_states: dict[tuple[str, int], dict[str, object]],
) -> tuple[list[dict[str, object]], list[str], str, dict[str, object]]:
    user_id = str(session["user_id"])
    target_position = int(session["target_position"])
    target_asin = str(session["target_asin"])
    candidate_asins = [str(value) for value in session["candidate_asins"]]

    if user_id not in histories:
        raise ValueError(f"Session user {user_id!r} absent from canonical histories")
    history = histories[user_id]
    target_index = target_position - 1
    if target_index < 1 or target_index >= len(history):
        raise ValueError(f"Invalid target position for {session['session_id']!r}")
    if str(history[target_index]["asin"]) != target_asin:
        raise ValueError(f"Frozen target mismatch for {session['session_id']!r}")
    if len(candidate_asins) != 20 or len(set(candidate_asins)) != 20:
        raise ValueError("Frozen candidate set must contain 20 unique items")
    if target_asin not in candidate_asins:
        raise ValueError("Ground-truth target missing from frozen candidate set")
    missing_titles = [asin for asin in candidate_asins if asin not in item_titles]
    if missing_titles:
        raise ValueError(f"Candidate titles missing: {missing_titles}")

    observed_history = history[:target_index]
    required_profile_position = target_position - 1
    key = (user_id, required_profile_position)
    if key not in profile_states:
        raise RuntimeError(
            f"Missing Phase 4 profile state for user={user_id}, position={required_profile_position}"
        )
    state = profile_states[key]
    if str(state.get("task_id", "")) != f"{user_id}:{required_profile_position}":
        raise RuntimeError(f"Unexpected profile-state task identity for {key}")
    if len(observed_history) != required_profile_position:
        raise RuntimeError("History/profile prefix length mismatch")
    return observed_history, candidate_asins, target_asin, state


def _finish_reason(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    value = choices[0].get("finish_reason")
    return value if isinstance(value, str) else None


def _publish(payload: dict[str, object], status_word: str) -> None:
    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: phase5 PURE recommender pilot {status_word.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 5 PURE recommender pilot")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config" / "phase5_pure_recommender_pilot.toml"),
    )
    parser.add_argument(
        "--llm-config",
        default=str(REPO_ROOT / "config" / "local_llm.toml"),
    )
    args = parser.parse_args()

    config = load_phase5_config(args.config)
    llm_config = load_local_llm_config(args.llm_config)

    for label, path in (
        ("items", config.input.items_path),
        ("interactions", config.input.interactions_path),
        ("sessions", config.input.sessions_path),
        ("profile states", config.input.profile_states_path),
    ):
        if not path.exists():
            raise FileNotFoundError(f"Required {label} artifact not found: {path}")

    item_titles = load_items(config.input.items_path)
    histories = load_histories(config.input.interactions_path)
    all_sessions = load_sessions(config.input.sessions_path)
    profile_states = _load_profile_states(config.input.profile_states_path)
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
            f"Configured model {llm_config.model!r} is not exposed by local server; visible={visible_models}"
        )

    output_dir = config.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.jsonl"
    summary_path = output_dir / "summary.json"
    if results_path.exists():
        results_path.unlink()

    print("=" * 96)
    print("PURE PHASE 5 — RECOMMENDER PILOT")
    print("=" * 96)
    print(f"Model                 : {llm_config.model}")
    print(f"Frozen sessions       : {len(all_sessions)}")
    print(f"Pilot sessions        : {len(sessions)}")
    print(f"Profile states        : {len(profile_states)}")
    print(f"Temperature           : {config.generation.temperature}")
    print(f"Max output tokens     : {config.generation.max_tokens}")
    print(f"Seed                  : {config.generation.seed}")
    print("Ranking output        : structured complete permutation of candidate numbers")
    print()

    rows: list[dict[str, object]] = []
    ranks_by_user: dict[str, list[int]] = defaultdict(list)
    prompt_tokens_list: list[int] = []
    completion_tokens_list: list[int] = []
    latencies: list[float] = []
    failures: list[dict[str, object]] = []

    for ordinal, session in enumerate(sessions, start=1):
        session_id = str(session["session_id"])
        raw_content = ""
        started = time.perf_counter()
        try:
            history, candidate_asins, target_asin, state = _validate_session(
                session, histories, item_titles, profile_states
            )
            profile_mapping = state.get("profile")
            if not isinstance(profile_mapping, dict):
                raise ValueError(f"Invalid profile mapping in state for {session_id}")
            profile = profile_from_mapping(profile_mapping)
            messages = build_pure_recommender_messages(
                history=history,
                profile=profile,
                candidate_asins=candidate_asins,
                item_titles=item_titles,
            )
            response = client.chat_completion(
                model=llm_config.model,
                messages=messages,
                temperature=config.generation.temperature,
                max_tokens=config.generation.max_tokens,
                seed=config.generation.seed,
                response_format=pure_recommender_response_format(len(candidate_asins)),
            )
            elapsed = time.perf_counter() - started
            raw_content = response.content
            ranking = parse_complete_ranking(raw_content, candidate_asins)
            rank = target_rank(ranking, target_asin)
            ndcg = ndcg_at_ks_from_rank(rank)
            usage = dict(response.usage) if response.usage else {}
            prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
            completion_tokens = int(usage.get("completion_tokens", 0) or 0)
            prompt_tokens_list.append(prompt_tokens)
            completion_tokens_list.append(completion_tokens)
            latencies.append(elapsed)
            user_id = str(session["user_id"])
            ranks_by_user[user_id].append(rank)

            row: dict[str, object] = {
                "status": "ok",
                "session_id": session_id,
                "user_id": user_id,
                "target_position": int(session["target_position"]),
                "profile_state_task_id": state.get("task_id"),
                "history_length": len(history),
                "profile_counts": {
                    "likes": len(profile.likes),
                    "dislikes": len(profile.dislikes),
                    "key_features": len(profile.key_features),
                    "total": len(profile.likes) + len(profile.dislikes) + len(profile.key_features),
                },
                "target_rank": rank,
                "ndcg": {str(k): value for k, value in ndcg.items()},
                "finish_reason": _finish_reason(response.raw),
                "latency_seconds": elapsed,
                "usage": usage,
                "ranking": ranking,
            }
            rows.append(row)
            _append_jsonl(results_path, row)
            print(
                f"[{ordinal:02d}/{len(sessions):02d}] {session_id}: "
                f"history={len(history)} profile={row['profile_counts']['total']} "
                f"rank={rank} prompt_tokens={prompt_tokens} latency={elapsed:.2f}s"
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            failure = {
                "status": "error",
                "session_id": session_id,
                "user_id": str(session.get("user_id", "")),
                "error": str(exc),
                "raw_response": raw_content,
                "latency_seconds": elapsed,
            }
            rows.append(failure)
            failures.append(failure)
            _append_jsonl(results_path, failure)
            print(f"[{ordinal:02d}/{len(sessions):02d}] {session_id}: ERROR: {exc}")
            if config.experiment.fail_fast:
                break

    ok_rows = [row for row in rows if row.get("status") == "ok"]
    metrics = (
        aggregate_user_ndcg(ranks_by_user)
        if ranks_by_user
        else {1: 0.0, 5: 0.0, 10: 0.0, 20: 0.0}
    )
    status = "PASS" if len(ok_rows) == len(sessions) and not failures else "INCOMPLETE"
    summary: dict[str, object] = {
        "component": "PURE Recommender",
        "run_version": "pilot_v1",
        "model": llm_config.model,
        "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
        "frozen_sessions": len(all_sessions),
        "requested_sessions": len(sessions),
        "successful_sessions": len(ok_rows),
        "failed_sessions": len(failures),
        "users_in_successful_sessions": len(ranks_by_user),
        "profile_state_alignment": "target_position_minus_one",
        "generation": {
            "temperature": config.generation.temperature,
            "max_tokens": config.generation.max_tokens,
            "seed": config.generation.seed,
            "structured_output": "complete_numbered_candidate_ranking_json_schema",
        },
        "ndcg": {str(k): value for k, value in metrics.items()},
        "prompt_tokens": {
            "total": sum(prompt_tokens_list),
            "mean": statistics.mean(prompt_tokens_list) if prompt_tokens_list else 0.0,
            "max": max(prompt_tokens_list) if prompt_tokens_list else 0,
        },
        "completion_tokens": {
            "total": sum(completion_tokens_list),
            "mean": statistics.mean(completion_tokens_list) if completion_tokens_list else 0.0,
        },
        "latency": {
            "total_seconds": sum(latencies),
            "mean_seconds": statistics.mean(latencies) if latencies else 0.0,
        },
        "status": status,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    handoff_rows = [
        {
            "status": row.get("status"),
            "session_id": row.get("session_id"),
            "user_id": row.get("user_id"),
            "target_position": row.get("target_position"),
            "profile_state_task_id": row.get("profile_state_task_id"),
            "history_length": row.get("history_length"),
            "profile_counts": row.get("profile_counts"),
            "target_rank": row.get("target_rank"),
            "ndcg": row.get("ndcg"),
            "finish_reason": row.get("finish_reason"),
            "latency_seconds": row.get("latency_seconds"),
            "usage": row.get("usage"),
            "error": row.get("error"),
            "raw_response": row.get("raw_response") if row.get("status") != "ok" else None,
        }
        for row in rows
    ]
    _publish(
        {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "summary": summary,
            "rows": handoff_rows,
        },
        status,
    )

    print()
    print("=" * 96)
    print("PHASE 5 PURE RECOMMENDER PILOT SUMMARY")
    print("=" * 96)
    print(f"successful_sessions : {len(ok_rows)}/{len(sessions)}")
    print(f"failed_sessions     : {len(failures)}")
    for k in (1, 5, 10, 20):
        print(f"NDCG@{k:<2}             : {metrics[k]:.6f}")
    print(f"mean_prompt_tokens  : {summary['prompt_tokens']['mean']:.2f}")
    print(f"mean_latency_sec    : {summary['latency']['mean_seconds']:.3f}")
    print(f"status              : {status}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
