"""Run Phase 5 PURE recommender hybrid-output pilot v4.

The policy is uniform for every session:
1. ask for the direct 20-item ranking-array serialization;
2. validate it with the frozen strict complete-permutation parser;
3. only when that model output is structurally invalid, discard it and issue one
   fresh rank-map request using the same frozen history/profile/candidates and
   generation settings;
4. accept the rank-map result only if its strict parser validates a complete
   permutation.

The invalid direct response is never edited, repaired, or shown to the fallback
call. API/validation failures do not trigger the serialization fallback. This
pilot covers the same eight diagnostic sessions used by the scored and rank-map
pilots so complementary failure behavior can be tested explicitly.
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

from pure_recommender.baselines import parse_complete_ranking, target_rank
from pure_recommender.evaluation.metrics import aggregate_user_ndcg, ndcg_at_ks_from_rank
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase2 import load_histories, load_items, load_sessions
from pure_recommender.phase5 import load_phase5_config
from pure_recommender.pure import (
    build_pure_recommender_messages,
    build_pure_recommender_rankmap_messages,
    parse_candidate_rankmap,
    profile_from_mapping,
    pure_recommender_rankmap_response_format,
    pure_recommender_response_format,
)
import run_phase5_pure_recommender as shared_runner


EXPERIMENT = "phase5_pure_recommender_hybrid_pilot_v4"
CONFIG_PATH = REPO_ROOT / "config" / "phase5_pure_recommender_hybrid_pilot.toml"

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
KNOWN_RANKMAP_STANDALONE_FAILURES = {
    "A2GSRMMRODQ4JH:4",
    "A2GSRMMRODQ4JH:6",
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
        commit_message=f"handoff: phase5 hybrid pilot v4 {status_word.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def _usage_dict(response: object) -> dict[str, object]:
    usage = getattr(response, "usage", None)
    return dict(usage) if usage else {}


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
        raise RuntimeError(f"Hybrid pilot target sessions missing: {missing_ids}")
    if len(sessions) != len(TARGET_SESSION_IDS):
        raise RuntimeError(f"Expected {len(TARGET_SESSION_IDS)} pilot sessions; found {len(sessions)}")

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

    print("=" * 104)
    print("PURE PHASE 5 — HYBRID OUTPUT PILOT V4")
    print("=" * 104)
    print(f"Model                     : {llm_config.model}")
    print(f"Pilot sessions            : {len(sessions)}")
    print(f"Known direct failures     : {len(KNOWN_DIRECT_FAILURES)}")
    print(f"Known rank-map failures   : {len(KNOWN_RANKMAP_STANDALONE_FAILURES)}")
    print(f"Temperature               : {config.generation.temperature}")
    print(f"Seed                      : {config.generation.seed}")
    print(f"Max output tokens         : {config.generation.max_tokens}")
    print("Primary                   : direct ranking array")
    print("Fallback                  : one fresh rank-map request after direct parse failure only")
    print("Post-generation repair    : NONE")
    print()

    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    ranks_by_user: dict[str, list[int]] = defaultdict(list)
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_reported_tokens = 0
    total_request_latency = 0.0
    final_session_latencies: list[float] = []
    fallback_attempts = 0
    fallback_successes = 0
    direct_successes = 0
    known_direct_recovered = 0
    known_rankmap_failure_primary_successes = 0

    for ordinal, session in enumerate(sessions, start=1):
        session_id = str(session["session_id"])
        session_started = time.perf_counter()
        direct_raw = ""
        fallback_raw = ""
        direct_error: str | None = None
        direct_usage: dict[str, object] = {}
        fallback_usage: dict[str, object] = {}
        direct_latency = 0.0
        fallback_latency = 0.0
        protocol_used: str | None = None

        try:
            history, candidate_asins, target_asin, state = shared_runner._validate_session(
                session, histories, item_titles, profile_states
            )
            profile_mapping = state.get("profile")
            if not isinstance(profile_mapping, dict):
                raise ValueError(f"Invalid profile mapping in state for {session_id}")
            profile = profile_from_mapping(profile_mapping)

            direct_messages = build_pure_recommender_messages(
                history=history,
                profile=profile,
                candidate_asins=candidate_asins,
                item_titles=item_titles,
            )
            direct_started = time.perf_counter()
            direct_response = client.chat_completion(
                model=llm_config.model,
                messages=direct_messages,
                temperature=config.generation.temperature,
                max_tokens=config.generation.max_tokens,
                seed=config.generation.seed,
                response_format=pure_recommender_response_format(len(candidate_asins)),
            )
            direct_latency = time.perf_counter() - direct_started
            total_request_latency += direct_latency
            direct_raw = direct_response.content
            direct_usage = _usage_dict(direct_response)
            total_prompt_tokens += int(direct_usage.get("prompt_tokens", 0) or 0)
            total_completion_tokens += int(direct_usage.get("completion_tokens", 0) or 0)
            total_reported_tokens += int(direct_usage.get("total_tokens", 0) or 0)

            try:
                ranking = parse_complete_ranking(direct_raw, candidate_asins)
                protocol_used = "direct_primary"
                direct_successes += 1
                if session_id in KNOWN_RANKMAP_STANDALONE_FAILURES:
                    known_rankmap_failure_primary_successes += 1
            except ValueError as exc:
                direct_error = str(exc)
                fallback_attempts += 1

                rankmap_messages = build_pure_recommender_rankmap_messages(
                    history=history,
                    profile=profile,
                    candidate_asins=candidate_asins,
                    item_titles=item_titles,
                )
                fallback_started = time.perf_counter()
                fallback_response = client.chat_completion(
                    model=llm_config.model,
                    messages=rankmap_messages,
                    temperature=config.generation.temperature,
                    max_tokens=config.generation.max_tokens,
                    seed=config.generation.seed,
                    response_format=pure_recommender_rankmap_response_format(len(candidate_asins)),
                )
                fallback_latency = time.perf_counter() - fallback_started
                total_request_latency += fallback_latency
                fallback_raw = fallback_response.content
                fallback_usage = _usage_dict(fallback_response)
                total_prompt_tokens += int(fallback_usage.get("prompt_tokens", 0) or 0)
                total_completion_tokens += int(fallback_usage.get("completion_tokens", 0) or 0)
                total_reported_tokens += int(fallback_usage.get("total_tokens", 0) or 0)

                ranking, _rank_map = parse_candidate_rankmap(fallback_raw, candidate_asins)
                protocol_used = "rankmap_fallback"
                fallback_successes += 1
                if session_id in KNOWN_DIRECT_FAILURES:
                    known_direct_recovered += 1

            rank = target_rank(ranking, target_asin)
            ndcg = ndcg_at_ks_from_rank(rank)
            user_id = str(session["user_id"])
            ranks_by_user[user_id].append(rank)
            session_elapsed = time.perf_counter() - session_started
            final_session_latencies.append(session_elapsed)

            row: dict[str, object] = {
                "status": "ok",
                "session_id": session_id,
                "user_id": user_id,
                "target_position": int(session["target_position"]),
                "profile_state_task_id": state.get("task_id"),
                "history_length": len(history),
                "known_direct_ranking_failure": session_id in KNOWN_DIRECT_FAILURES,
                "known_rankmap_standalone_failure": session_id in KNOWN_RANKMAP_STANDALONE_FAILURES,
                "protocol_used": protocol_used,
                "direct_validation_error": direct_error,
                "target_rank": rank,
                "ndcg": {str(k): value for k, value in ndcg.items()},
                "direct_finish_reason": shared_runner._finish_reason(direct_response.raw),
                "fallback_finish_reason": (
                    shared_runner._finish_reason(fallback_response.raw)
                    if protocol_used == "rankmap_fallback"
                    else None
                ),
                "direct_latency_seconds": direct_latency,
                "fallback_latency_seconds": fallback_latency,
                "session_latency_seconds": session_elapsed,
                "direct_usage": direct_usage,
                "fallback_usage": fallback_usage if protocol_used == "rankmap_fallback" else None,
                "ranking": ranking,
            }
            rows.append(row)
            _append_jsonl(results_path, row)
            print(
                f"[{ordinal:02d}/{len(sessions):02d}] {session_id}: "
                f"protocol={protocol_used} rank={rank} "
                f"direct={direct_latency:.2f}s fallback={fallback_latency:.2f}s"
            )
        except Exception as exc:
            session_elapsed = time.perf_counter() - session_started
            failure = {
                "status": "error",
                "session_id": session_id,
                "user_id": str(session.get("user_id", "")),
                "known_direct_ranking_failure": session_id in KNOWN_DIRECT_FAILURES,
                "known_rankmap_standalone_failure": session_id in KNOWN_RANKMAP_STANDALONE_FAILURES,
                "protocol_used": protocol_used,
                "direct_validation_error": direct_error,
                "error": str(exc),
                "direct_raw_response": direct_raw,
                "fallback_raw_response": fallback_raw,
                "direct_latency_seconds": direct_latency,
                "fallback_latency_seconds": fallback_latency,
                "session_latency_seconds": session_elapsed,
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

    status = (
        "PASS"
        if len(ok_rows) == len(sessions)
        and not failures
        and known_direct_recovered == len(KNOWN_DIRECT_FAILURES)
        and known_rankmap_failure_primary_successes == len(KNOWN_RANKMAP_STANDALONE_FAILURES)
        else "INCOMPLETE"
    )

    summary: dict[str, object] = {
        "component": "PURE Recommender",
        "run_version": "hybrid_pilot_v4",
        "model": llm_config.model,
        "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
        "frozen_sessions": len(all_sessions),
        "requested_sessions": len(sessions),
        "successful_sessions": len(ok_rows),
        "failed_sessions": len(failures),
        "users_in_successful_sessions": len(ranks_by_user),
        "profile_state_alignment": "target_position_minus_one",
        "output_protocol": {
            "primary": "direct_complete_numbered_candidate_ranking",
            "fallback_condition": "strict_direct_parser_failure_only",
            "fallback": "fresh_candidate_rank_map_request",
            "invalid_primary_shown_to_fallback": False,
            "max_fallback_requests_per_session": 1,
            "deterministic_post_generation_repair": False,
        },
        "generation": {
            "temperature": config.generation.temperature,
            "max_tokens": config.generation.max_tokens,
            "seed": config.generation.seed,
        },
        "protocol_counts": {
            "direct_primary_successes": direct_successes,
            "fallback_attempts": fallback_attempts,
            "fallback_successes": fallback_successes,
        },
        "diagnostic_cases": {
            "known_direct_failures_tested": len(KNOWN_DIRECT_FAILURES),
            "known_direct_failures_recovered_by_fallback": known_direct_recovered,
            "known_rankmap_standalone_failures_tested": len(KNOWN_RANKMAP_STANDALONE_FAILURES),
            "known_rankmap_standalone_failures_succeeded_on_primary": known_rankmap_failure_primary_successes,
        },
        "ndcg": {str(k): value for k, value in metrics.items()},
        "usage_totals_all_requests": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_reported_tokens,
        },
        "latency": {
            "total_request_seconds": total_request_latency,
            "mean_final_session_seconds": (
                statistics.mean(final_session_latencies) if final_session_latencies else 0.0
            ),
        },
        "status": status,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    handoff_rows = [
        {
            "status": row.get("status"),
            "session_id": row.get("session_id"),
            "known_direct_ranking_failure": row.get("known_direct_ranking_failure"),
            "known_rankmap_standalone_failure": row.get("known_rankmap_standalone_failure"),
            "protocol_used": row.get("protocol_used"),
            "direct_validation_error": row.get("direct_validation_error"),
            "target_rank": row.get("target_rank"),
            "direct_latency_seconds": row.get("direct_latency_seconds"),
            "fallback_latency_seconds": row.get("fallback_latency_seconds"),
            "session_latency_seconds": row.get("session_latency_seconds"),
            "error": row.get("error"),
            "direct_raw_response": row.get("direct_raw_response") if row.get("status") != "ok" else None,
            "fallback_raw_response": row.get("fallback_raw_response") if row.get("status") != "ok" else None,
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
    print("=" * 104)
    print("PHASE 5 HYBRID OUTPUT PILOT V4 SUMMARY")
    print("=" * 104)
    print(f"successful_sessions                    : {len(ok_rows)}/{len(sessions)}")
    print(f"direct_primary_successes               : {direct_successes}")
    print(f"fallback_attempts/successes            : {fallback_attempts}/{fallback_successes}")
    print(
        "known_direct_failures_recovered        : "
        f"{known_direct_recovered}/{len(KNOWN_DIRECT_FAILURES)}"
    )
    print(
        "known_rankmap_failures_primary_success : "
        f"{known_rankmap_failure_primary_successes}/{len(KNOWN_RANKMAP_STANDALONE_FAILURES)}"
    )
    for k in (1, 5, 10, 20):
        print(f"NDCG@{k:<2}                               : {metrics[k]:.6f}")
    print(f"status                                  : {status}")
    print(f"results                                 : {results_path}")
    print(f"summary                                 : {summary_path}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
