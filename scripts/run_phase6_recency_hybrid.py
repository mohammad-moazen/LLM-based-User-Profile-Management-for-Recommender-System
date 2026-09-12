"""Run the final controlled Recency-Focused baseline with hybrid output validation.

The recommendation method remains Recency-Focused: the model sees the same
chronological purchase-history titles and frozen candidate titles as Sequential,
plus the paper-aligned explicit emphasis on the most recent observed purchase.
Reviews, ratings, PURE profiles, target markers, and future information remain
excluded.

Mechanical output policy matches final PURE and final Sequential:
1. direct numbered ranking-array request;
2. strict complete-permutation validation;
3. only after a structural direct-parser failure, one fresh Recency rank-map request;
4. strict rank-map validation;
5. no post-generation candidate repair.
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

from pure_recommender.baselines import build_recency_messages, parse_complete_ranking, target_rank
from pure_recommender.baselines.recency_rankmap import build_recency_rankmap_messages
from pure_recommender.evaluation.metrics import aggregate_user_ndcg, ndcg_at_ks_from_rank
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase2 import load_histories, load_items, load_phase2_config, load_sessions
from pure_recommender.pure import (
    parse_candidate_rankmap,
    pure_recommender_rankmap_response_format,
    pure_recommender_response_format,
)
import run_phase6_sequential_hybrid as shared


EXPERIMENT = "phase6_recency_hybrid_full_v1"
RUN_VERSION = "recency_hybrid_full_v1"
CONFIG_PATH = REPO_ROOT / "config" / "phase6_recency_hybrid.toml"


def _publish(payload: dict[str, object], status_word: str) -> None:
    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: phase6 Recency hybrid {status_word.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")


def main() -> int:
    config = load_phase2_config(CONFIG_PATH)
    llm_config = load_local_llm_config(REPO_ROOT / "config" / "local_llm.toml")

    for label, path in (
        ("items", config.input.items_path),
        ("interactions", config.input.interactions_path),
        ("sessions", config.input.sessions_path),
    ):
        if not path.exists():
            raise FileNotFoundError(f"Required frozen Phase 1 {label} artifact not found: {path}")

    item_titles = load_items(config.input.items_path)
    histories = load_histories(config.input.interactions_path)
    all_sessions = load_sessions(config.input.sessions_path)
    sessions = all_sessions if config.experiment.max_sessions == 0 else all_sessions[: config.experiment.max_sessions]

    if len(sessions) != 94:
        raise RuntimeError(f"Final Recency workload must contain 94 frozen sessions; found {len(sessions)}")
    if config.experiment.resume:
        raise RuntimeError("Final Recency rerun must start cleanly with experiment.resume=false")

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

    print("=" * 108)
    print("PHASE 6 — FINAL RECENCY-FOCUSED BASELINE / HYBRID OUTPUT V1")
    print("=" * 108)
    print(f"Model                     : {llm_config.model}")
    print(f"Frozen sessions           : {len(sessions)}")
    print(f"Temperature               : {config.generation.temperature}")
    print(f"Seed                      : {config.generation.seed}")
    print(f"Max output tokens         : {config.generation.max_tokens}")
    print("Method inputs             : purchase titles + explicit most-recent-item emphasis + candidates")
    print("Primary                   : direct ranking array with structured schema")
    print("Fallback                  : one fresh Recency rank-map request after structural parse failure")
    print("Post-generation repair    : NONE")
    print()

    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    fallback_rows: list[dict[str, object]] = []
    ranks_by_user: dict[str, list[int]] = defaultdict(list)

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_reported_tokens = 0
    prompt_tokens_per_request: list[int] = []
    completion_tokens_per_request: list[int] = []
    request_latencies: list[float] = []
    session_latencies: list[float] = []

    direct_successes = 0
    fallback_attempts = 0
    fallback_successes = 0

    for ordinal, session in enumerate(sessions, start=1):
        session_id = str(session["session_id"])
        session_started = time.perf_counter()
        direct_raw = ""
        fallback_raw = ""
        direct_error: str | None = None
        direct_latency = 0.0
        fallback_latency = 0.0
        direct_usage: dict[str, object] = {}
        fallback_usage: dict[str, object] = {}
        protocol_used: str | None = None
        direct_response = None
        fallback_response = None

        try:
            history, candidate_asins, target_asin = shared._validate_session(session, histories, item_titles)
            recent_title = str(history[-1]["title"])

            direct_messages = build_recency_messages(
                history=history,
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
            request_latencies.append(direct_latency)
            direct_raw = direct_response.content
            direct_usage = shared._usage_dict(direct_response)

            pt = int(direct_usage.get("prompt_tokens", 0) or 0)
            ct = int(direct_usage.get("completion_tokens", 0) or 0)
            tt = int(direct_usage.get("total_tokens", 0) or 0)
            prompt_tokens_per_request.append(pt)
            completion_tokens_per_request.append(ct)
            total_prompt_tokens += pt
            total_completion_tokens += ct
            total_reported_tokens += tt

            try:
                ranking = parse_complete_ranking(direct_raw, candidate_asins)
                protocol_used = "direct_primary"
                direct_successes += 1
            except ValueError as exc:
                direct_error = str(exc)
                fallback_attempts += 1

                fallback_messages = build_recency_rankmap_messages(
                    history=history,
                    candidate_asins=candidate_asins,
                    item_titles=item_titles,
                )
                fallback_started = time.perf_counter()
                fallback_response = client.chat_completion(
                    model=llm_config.model,
                    messages=fallback_messages,
                    temperature=config.generation.temperature,
                    max_tokens=config.generation.max_tokens,
                    seed=config.generation.seed,
                    response_format=pure_recommender_rankmap_response_format(len(candidate_asins)),
                )
                fallback_latency = time.perf_counter() - fallback_started
                request_latencies.append(fallback_latency)
                fallback_raw = fallback_response.content
                fallback_usage = shared._usage_dict(fallback_response)

                pt = int(fallback_usage.get("prompt_tokens", 0) or 0)
                ct = int(fallback_usage.get("completion_tokens", 0) or 0)
                tt = int(fallback_usage.get("total_tokens", 0) or 0)
                prompt_tokens_per_request.append(pt)
                completion_tokens_per_request.append(ct)
                total_prompt_tokens += pt
                total_completion_tokens += ct
                total_reported_tokens += tt

                ranking, _rank_map = parse_candidate_rankmap(fallback_raw, candidate_asins)
                protocol_used = "rankmap_fallback"
                fallback_successes += 1

            rank = target_rank(ranking, target_asin)
            ndcg = ndcg_at_ks_from_rank(rank)
            user_id = str(session["user_id"])
            ranks_by_user[user_id].append(rank)
            session_elapsed = time.perf_counter() - session_started
            session_latencies.append(session_elapsed)

            row: dict[str, object] = {
                "status": "ok",
                "session_id": session_id,
                "user_id": user_id,
                "target_position": int(session["target_position"]),
                "history_length": len(history),
                "recent_item_title": recent_title,
                "protocol_used": protocol_used,
                "direct_validation_error": direct_error,
                "target_rank": rank,
                "ndcg": {str(k): value for k, value in ndcg.items()},
                "direct_finish_reason": shared._finish_reason(direct_response.raw),
                "fallback_finish_reason": shared._finish_reason(fallback_response.raw) if fallback_response is not None else None,
                "direct_latency_seconds": direct_latency,
                "fallback_latency_seconds": fallback_latency,
                "session_latency_seconds": session_elapsed,
                "direct_usage": direct_usage,
                "fallback_usage": fallback_usage if fallback_response is not None else None,
                "ranking": ranking,
            }
            rows.append(row)
            if protocol_used == "rankmap_fallback":
                fallback_rows.append(row)
            shared._append_jsonl(results_path, row)
            print(
                f"[{ordinal:02d}/{len(sessions):02d}] {session_id}: "
                f"protocol={protocol_used} rank={rank} direct={direct_latency:.2f}s "
                f"fallback={fallback_latency:.2f}s"
            )
        except Exception as exc:
            session_elapsed = time.perf_counter() - session_started
            failure = {
                "status": "error",
                "session_id": session_id,
                "user_id": str(session.get("user_id", "")),
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
            shared._append_jsonl(results_path, failure)
            print(f"[{ordinal:02d}/{len(sessions):02d}] {session_id}: ERROR: {exc}")
            if config.experiment.fail_fast:
                break

    ok_rows = [row for row in rows if row.get("status") == "ok"]
    metrics = aggregate_user_ndcg(ranks_by_user) if ranks_by_user else {1: 0.0, 5: 0.0, 10: 0.0, 20: 0.0}
    status = "PASS" if len(ok_rows) == len(sessions) and not failures else "INCOMPLETE"

    summary: dict[str, object] = {
        "baseline": "Recency-Focused",
        "experiment": EXPERIMENT,
        "run_version": RUN_VERSION,
        "model": llm_config.model,
        "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
        "frozen_sessions": len(all_sessions),
        "requested_sessions": len(sessions),
        "successful_sessions": len(ok_rows),
        "failed_sessions": len(failures),
        "users_in_successful_sessions": len(ranks_by_user),
        "method_inputs": "chronological_purchase_titles_plus_explicit_most_recent_item_emphasis_and_frozen_candidate_titles",
        "output_protocol": {
            "primary": "direct_complete_numbered_candidate_ranking",
            "fallback_condition": "strict_direct_parser_failure_only",
            "fallback": "fresh_recency_candidate_rank_map_request",
            "invalid_primary_shown_to_fallback": False,
            "max_fallback_requests_per_session": 1,
            "deterministic_post_generation_repair": False,
        },
        "generation": {
            "temperature": config.generation.temperature,
            "max_tokens": config.generation.max_tokens,
            "seed": config.generation.seed,
            "direct_structured_output": "complete_numbered_candidate_ranking_json_schema",
            "fallback_structured_output": "complete_candidate_rank_map_json_schema",
        },
        "protocol_counts": {
            "direct_primary_successes": direct_successes,
            "fallback_attempts": fallback_attempts,
            "fallback_successes": fallback_successes,
        },
        "ndcg": {str(k): value for k, value in metrics.items()},
        "usage_totals_all_requests": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_reported_tokens,
            "request_count": len(prompt_tokens_per_request),
            "mean_prompt_tokens": statistics.mean(prompt_tokens_per_request) if prompt_tokens_per_request else 0.0,
            "max_prompt_tokens": max(prompt_tokens_per_request) if prompt_tokens_per_request else 0,
            "mean_completion_tokens": statistics.mean(completion_tokens_per_request) if completion_tokens_per_request else 0.0,
        },
        "latency": {
            "total_request_seconds": sum(request_latencies),
            "mean_request_seconds": statistics.mean(request_latencies) if request_latencies else 0.0,
            "mean_session_seconds": statistics.mean(session_latencies) if session_latencies else 0.0,
            "median_session_seconds": statistics.median(session_latencies) if session_latencies else 0.0,
        },
        "status": status,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    compact_fallback_rows = [
        {
            "status": row.get("status"),
            "session_id": row.get("session_id"),
            "user_id": row.get("user_id"),
            "target_position": row.get("target_position"),
            "protocol_used": row.get("protocol_used"),
            "direct_validation_error": row.get("direct_validation_error"),
            "target_rank": row.get("target_rank"),
            "direct_finish_reason": row.get("direct_finish_reason"),
            "fallback_finish_reason": row.get("fallback_finish_reason"),
            "direct_latency_seconds": row.get("direct_latency_seconds"),
            "fallback_latency_seconds": row.get("fallback_latency_seconds"),
        }
        for row in fallback_rows
    ]
    compact_failures = [
        {
            "status": row.get("status"),
            "session_id": row.get("session_id"),
            "user_id": row.get("user_id"),
            "protocol_used": row.get("protocol_used"),
            "direct_validation_error": row.get("direct_validation_error"),
            "error": row.get("error"),
        }
        for row in failures
    ]

    _publish(
        {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "summary": summary,
            "fallback_rows": compact_fallback_rows,
            "errors": compact_failures,
        },
        status,
    )

    print()
    print("=" * 108)
    print("PHASE 6 FINAL RECENCY-FOCUSED SUMMARY")
    print("=" * 108)
    print(f"successful_sessions : {len(ok_rows)}/{len(sessions)}")
    print(f"failed_sessions     : {len(failures)}")
    print(f"direct_successes    : {direct_successes}")
    print(f"fallbacks           : {fallback_successes}/{fallback_attempts}")
    for k in (1, 5, 10, 20):
        print(f"NDCG@{k:<2}             : {metrics[k]:.6f}")
    print(f"status              : {status}")
    print(f"results             : {results_path}")
    print(f"summary             : {summary_path}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
