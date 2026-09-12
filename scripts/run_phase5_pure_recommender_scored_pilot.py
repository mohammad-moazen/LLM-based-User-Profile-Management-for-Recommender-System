"""Run Phase 5 PURE recommender scored-output pilot v2.

This pilot preserves the frozen Phase 1 sessions, Phase 4 profile states, model,
generation settings, history/profile serialization, and candidate titles. The only
intentional change is machine-readable output serialization: instead of asking the
local backend to emit a unique 20-item permutation directly, the model emits one
required purchase-likelihood score for each numbered candidate. The runner then
sorts those model scores deterministically to obtain the ranking.

Coverage deliberately includes the original six successful pilot sessions plus
the two sessions that failed the first full direct-ranking attempt. This validates
both ordinary behavior and the exact structural failure cases before any new
94-session evaluation is attempted.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pure_recommender.baselines import target_rank
from pure_recommender.evaluation.metrics import aggregate_user_ndcg, ndcg_at_ks_from_rank
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase2 import load_histories, load_items, load_sessions
from pure_recommender.phase5 import load_phase5_config
from pure_recommender.pure import (
    build_pure_recommender_score_messages,
    parse_candidate_scores,
    profile_from_mapping,
    pure_recommender_score_response_format,
)
import run_phase5_pure_recommender as shared_runner


EXPERIMENT = "phase5_pure_recommender_scored_pilot_v2"
CONFIG_PATH = REPO_ROOT / "config" / "phase5_pure_recommender_scored_pilot.toml"

# First six direct-ranking pilot sessions plus both direct-ranking full-run failures.
TARGET_SESSION_IDS = (
    "A24ZRTTC3SPX8C:4",
    "A24ZRTTC3SPX8C:5",
    "A2GSRMMRODQ4JH:4",
    "A2GSRMMRODQ4JH:5",
    "A2GSRMMRODQ4JH:6",
    "A2GSRMMRODQ4JH:7",
    "A3RQZ1J5F5G104:10",
    "A26C4UAI3IXYF:6",
)
KNOWN_DIRECT_FAILURES = {
    "A3RQZ1J5F5G104:10",
    "A26C4UAI3IXYF:6",
}


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _publish(payload: dict[str, object], status_word: str) -> None:
    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: phase5 scored pilot v2 {status_word.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def main() -> int:
    config = load_phase5_config(CONFIG_PATH)
    llm_config = load_local_llm_config(REPO_ROOT / "config" / "local_llm.toml")

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
    profile_states = shared_runner._load_profile_states(config.input.profile_states_path)

    target_set = set(TARGET_SESSION_IDS)
    sessions = [session for session in all_sessions if str(session["session_id"]) in target_set]
    found_ids = {str(session["session_id"]) for session in sessions}
    missing_ids = sorted(target_set - found_ids)
    if missing_ids:
        raise RuntimeError(f"Scored pilot target sessions missing from frozen workload: {missing_ids}")
    if len(sessions) != len(TARGET_SESSION_IDS):
        raise RuntimeError(
            f"Expected {len(TARGET_SESSION_IDS)} unique pilot sessions; found {len(sessions)}"
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

    print("=" * 100)
    print("PURE PHASE 5 — SCORED-OUTPUT PILOT V2")
    print("=" * 100)
    print(f"Model                  : {llm_config.model}")
    print(f"Frozen sessions        : {len(all_sessions)}")
    print(f"Pilot sessions         : {len(sessions)}")
    print(f"Known direct failures  : {len(KNOWN_DIRECT_FAILURES)}")
    print(f"Profile states         : {len(profile_states)}")
    print(f"Temperature            : {config.generation.temperature}")
    print(f"Seed                   : {config.generation.seed}")
    print(f"Max output tokens      : {config.generation.max_tokens}")
    print("Output protocol         : one required integer score per candidate; deterministic sort")
    print("Post-generation repair  : NONE")
    print()

    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    ranks_by_user: dict[str, list[int]] = defaultdict(list)
    prompt_tokens_list: list[int] = []
    completion_tokens_list: list[int] = []
    latencies: list[float] = []
    sessions_with_ties = 0
    total_tie_groups = 0
    total_tied_candidates = 0

    for ordinal, session in enumerate(sessions, start=1):
        session_id = str(session["session_id"])
        raw_content = ""
        started = time.perf_counter()
        try:
            history, candidate_asins, target_asin, state = shared_runner._validate_session(
                session,
                histories,
                item_titles,
                profile_states,
            )
            profile_mapping = state.get("profile")
            if not isinstance(profile_mapping, dict):
                raise ValueError(f"Invalid profile mapping in state for {session_id}")
            profile = profile_from_mapping(profile_mapping)
            messages = build_pure_recommender_score_messages(
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
                response_format=pure_recommender_score_response_format(len(candidate_asins)),
            )
            elapsed = time.perf_counter() - started
            raw_content = response.content
            ranking, scores, tie_group_count, tied_candidate_count = parse_candidate_scores(
                raw_content,
                candidate_asins,
            )
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
            if tie_group_count:
                sessions_with_ties += 1
            total_tie_groups += tie_group_count
            total_tied_candidates += tied_candidate_count

            target_candidate_number = candidate_asins.index(target_asin) + 1
            row: dict[str, object] = {
                "status": "ok",
                "session_id": session_id,
                "user_id": user_id,
                "target_position": int(session["target_position"]),
                "profile_state_task_id": state.get("task_id"),
                "history_length": len(history),
                "known_direct_ranking_failure": session_id in KNOWN_DIRECT_FAILURES,
                "target_candidate_number": target_candidate_number,
                "target_score": scores[target_candidate_number],
                "target_rank": rank,
                "ndcg": {str(k): value for k, value in ndcg.items()},
                "tie_group_count": tie_group_count,
                "tied_candidate_count": tied_candidate_count,
                "finish_reason": shared_runner._finish_reason(response.raw),
                "latency_seconds": elapsed,
                "usage": usage,
                "scores": {str(number): score for number, score in scores.items()},
                "ranking": ranking,
            }
            rows.append(row)
            _append_jsonl(results_path, row)
            print(
                f"[{ordinal:02d}/{len(sessions):02d}] {session_id}: "
                f"rank={rank} target_score={scores[target_candidate_number]} "
                f"ties={tie_group_count}/{tied_candidate_count} "
                f"prompt_tokens={prompt_tokens} latency={elapsed:.2f}s"
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            failure = {
                "status": "error",
                "session_id": session_id,
                "user_id": str(session.get("user_id", "")),
                "known_direct_ranking_failure": session_id in KNOWN_DIRECT_FAILURES,
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
    known_failure_rows = [
        row for row in rows if str(row.get("session_id", "")) in KNOWN_DIRECT_FAILURES
    ]
    known_failure_successes = sum(1 for row in known_failure_rows if row.get("status") == "ok")
    metrics = (
        aggregate_user_ndcg(ranks_by_user)
        if ranks_by_user
        else {1: 0.0, 5: 0.0, 10: 0.0, 20: 0.0}
    )
    status = (
        "PASS"
        if len(ok_rows) == len(sessions)
        and not failures
        and known_failure_successes == len(KNOWN_DIRECT_FAILURES)
        else "INCOMPLETE"
    )

    summary: dict[str, object] = {
        "component": "PURE Recommender",
        "run_version": "scored_pilot_v2",
        "model": llm_config.model,
        "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
        "frozen_sessions": len(all_sessions),
        "requested_sessions": len(sessions),
        "successful_sessions": len(ok_rows),
        "failed_sessions": len(failures),
        "users_in_successful_sessions": len(ranks_by_user),
        "profile_state_alignment": "target_position_minus_one",
        "output_protocol": {
            "model_output": "required_integer_purchase_likelihood_score_per_candidate",
            "score_range": [0, 1000],
            "ranking_derivation": "descending_model_score_then_frozen_candidate_number_ascending",
            "deterministic_post_generation_repair": False,
        },
        "generation": {
            "temperature": config.generation.temperature,
            "max_tokens": config.generation.max_tokens,
            "seed": config.generation.seed,
            "structured_output": "complete_candidate_score_object_json_schema",
        },
        "known_direct_ranking_failures": {
            "tested": len(KNOWN_DIRECT_FAILURES),
            "successful_under_scored_protocol": known_failure_successes,
        },
        "ties": {
            "sessions_with_ties": sessions_with_ties,
            "total_tie_groups": total_tie_groups,
            "total_tied_candidates": total_tied_candidates,
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
            "known_direct_ranking_failure": row.get("known_direct_ranking_failure"),
            "target_candidate_number": row.get("target_candidate_number"),
            "target_score": row.get("target_score"),
            "target_rank": row.get("target_rank"),
            "tie_group_count": row.get("tie_group_count"),
            "tied_candidate_count": row.get("tied_candidate_count"),
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
    print("=" * 100)
    print("PHASE 5 SCORED-OUTPUT PILOT V2 SUMMARY")
    print("=" * 100)
    print(f"successful_sessions             : {len(ok_rows)}/{len(sessions)}")
    print(f"known_direct_failures_recovered : {known_failure_successes}/{len(KNOWN_DIRECT_FAILURES)}")
    print(f"sessions_with_score_ties        : {sessions_with_ties}")
    for k in (1, 5, 10, 20):
        print(f"NDCG@{k:<2}                        : {metrics[k]:.6f}")
    print(f"mean_prompt_tokens             : {summary['prompt_tokens']['mean']:.2f}")
    print(f"mean_latency_sec               : {summary['latency']['mean_seconds']:.3f}")
    print(f"status                         : {status}")
    print(f"results                        : {results_path}")
    print(f"summary                        : {summary_path}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
