"""Run the frozen Phase 10B4 confirmatory PURE recommender.

The runner consumes exactly the immutable 767 Phase 9 sessions and the completed
Phase 10B2 profile states. It reuses the accepted Phase 5 PURE prompt and hybrid
mechanical output policy. Session-level resume is supported. Aggregate
confirmatory effectiveness metrics are written only to the local summary and are
withheld from the Git handoff until the paired Phase 10C analysis.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys
import time
import traceback
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (SRC_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pure_recommender.analysis.hardware_preflight import verify_phase9_freeze
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

EXPERIMENT = "phase10_confirmatory_pure_v1"
RUN_VERSION = "confirmatory_pure_hybrid_v1"
EXPECTED_USERS = 150
EXPECTED_SESSIONS = 767
EXPECTED_PROFILE_UPDATES = 1067
COHORT_SHA256 = "72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca"
SESSIONS_SHA256 = "0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859"

CONFIG_PATH = REPO_ROOT / "config/phase10_confirmatory_pure.toml"
COHORT_USERS_PATH = REPO_ROOT / "outputs/phase9_confirmatory_cohort_v1/cohort_users.json"
COHORT_SUMMARY_PATH = REPO_ROOT / "outputs/phase9_confirmatory_cohort_v1/cohort_summary.json"
PROFILE_SUMMARY_PATH = REPO_ROOT / "outputs/phase10_confirmatory_profile_updater_v2/summary.json"
RECENCY_SUMMARY_PATH = REPO_ROOT / "outputs/phase10_confirmatory_recency_v1/summary.json"


def _append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return value


def _load_latest_results(path: Path) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    if not path.exists():
        return latest
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError(f"Invalid result row at {path}:{line_number}")
            if row.get("run_version") != RUN_VERSION:
                raise RuntimeError(
                    f"Mixed-protocol result artifact detected at {path}:{line_number}"
                )
            session_id = row.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise RuntimeError(f"Missing session_id at {path}:{line_number}")
            latest[session_id] = row
    return latest


def _usage_dict(response: object) -> dict[str, object]:
    usage = getattr(response, "usage", None)
    return dict(usage) if usage else {}


def _finish_reason(raw: object) -> str | None:
    return shared_runner._finish_reason(raw)


def _publish(payload: dict[str, object], message: str) -> None:
    ok, detail = publish_handoff(REPO_ROOT, payload, commit_message=message, auto_push=True)
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {detail}")


def _preflight(config) -> tuple[dict[str, object], list[dict[str, object]], dict[tuple[str, int], dict[str, object]]]:
    freeze = verify_phase9_freeze(
        cohort_users_path=COHORT_USERS_PATH,
        sessions_path=config.input.sessions_path,
        cohort_summary_path=COHORT_SUMMARY_PATH,
        expected_cohort_sha256=COHORT_SHA256,
        expected_sessions_sha256=SESSIONS_SHA256,
        expected_users=EXPECTED_USERS,
        expected_sessions=EXPECTED_SESSIONS,
    )
    sessions = load_sessions(config.input.sessions_path)
    if len(sessions) != EXPECTED_SESSIONS:
        raise RuntimeError(f"Expected {EXPECTED_SESSIONS} frozen sessions; found {len(sessions)}")
    if len({str(row["user_id"]) for row in sessions}) != EXPECTED_USERS:
        raise RuntimeError("Frozen confirmatory session user count mismatch")

    profile_summary = _load_json(PROFILE_SUMMARY_PATH)
    if profile_summary.get("status") != "PASS":
        raise RuntimeError("Phase 10B2 final Profile Updater summary is not PASS")
    if int(profile_summary.get("successful_updates", -1)) != EXPECTED_PROFILE_UPDATES:
        raise RuntimeError("Phase 10B2 successful update count mismatch")
    if int(profile_summary.get("failed_updates", -1)) != 0:
        raise RuntimeError("Phase 10B2 contains unresolved profile failures")

    recency_summary = _load_json(RECENCY_SUMMARY_PATH)
    if recency_summary.get("status") != "PASS":
        raise RuntimeError("Phase 10B3 confirmatory Recency summary is not PASS")
    if int(recency_summary.get("successful_sessions", -1)) != EXPECTED_SESSIONS:
        raise RuntimeError("Phase 10B3 successful session count mismatch")
    if int(recency_summary.get("failed_sessions", -1)) != 0:
        raise RuntimeError("Phase 10B3 contains unresolved failures")

    profile_states = shared_runner._load_profile_states(config.input.profile_states_path)
    return freeze, sessions, profile_states


def main() -> int:
    try:
        config = load_phase5_config(CONFIG_PATH)
        llm_config = load_local_llm_config(REPO_ROOT / "config/local_llm.toml")
        freeze, sessions, profile_states = _preflight(config)

        item_titles = load_items(config.input.items_path)
        histories = load_histories(config.input.interactions_path)
        client = OpenAICompatibleLLMClient(
            base_url=llm_config.base_url,
            timeout_seconds=llm_config.timeout_seconds,
        )
        if llm_config.model not in client.list_models():
            raise RuntimeError(f"Configured model {llm_config.model!r} is not exposed by local server")

        output_dir = config.output.directory
        output_dir.mkdir(parents=True, exist_ok=True)
        results_path = output_dir / "results.jsonl"
        summary_path = output_dir / "summary.json"
        latest = _load_latest_results(results_path)

        frozen_session_ids = {str(row["session_id"]) for row in sessions}
        unexpected = sorted(set(latest) - frozen_session_ids)
        if unexpected:
            raise RuntimeError(f"PURE resume artifact contains non-frozen sessions: {unexpected[:10]}")
        successful_at_start = sum(row.get("status") == "ok" for row in latest.values())

        print("=" * 104)
        print("PHASE 10B4 — CONFIRMATORY PURE / HYBRID OUTPUT")
        print("=" * 104)
        print(f"Frozen sessions             : {len(sessions)}")
        print(f"Frozen users                : {EXPECTED_USERS}")
        print(f"Profile states available    : {len(profile_states)}")
        print(f"Existing successful sessions: {successful_at_start}")
        print("Runtime concurrency          : 1")
        print("Temperature / seed / max     : 0.0 / 42 / 512")
        print("Effectiveness handoff        : BLINDED until Phase 10C")
        print()

        new_calls = 0
        new_successes = 0
        failures_this_run: list[dict[str, object]] = []

        for ordinal, session in enumerate(sessions, start=1):
            session_id = str(session["session_id"])
            existing = latest.get(session_id)
            if existing is not None and existing.get("status") == "ok":
                continue

            direct_raw = ""
            fallback_raw = ""
            direct_error: str | None = None
            direct_response = None
            fallback_response = None
            direct_latency = 0.0
            fallback_latency = 0.0
            protocol_used: str | None = None
            session_started = time.perf_counter()

            try:
                history, candidate_asins, target_asin, state = shared_runner._validate_session(
                    session, histories, item_titles, profile_states
                )
                profile_mapping = state.get("profile")
                if not isinstance(profile_mapping, dict):
                    raise RuntimeError(f"Invalid profile mapping for {session_id}")
                profile = profile_from_mapping(profile_mapping)

                direct_messages = build_pure_recommender_messages(
                    history=history,
                    profile=profile,
                    candidate_asins=candidate_asins,
                    item_titles=item_titles,
                )
                started = time.perf_counter()
                direct_response = client.chat_completion(
                    model=llm_config.model,
                    messages=direct_messages,
                    temperature=0.0,
                    max_tokens=512,
                    seed=42,
                    response_format=pure_recommender_response_format(len(candidate_asins)),
                )
                new_calls += 1
                direct_latency = time.perf_counter() - started
                direct_raw = direct_response.content

                try:
                    ranking = parse_complete_ranking(direct_raw, candidate_asins)
                    protocol_used = "direct_primary"
                except ValueError as exc:
                    direct_error = str(exc)
                    fallback_messages = build_pure_recommender_rankmap_messages(
                        history=history,
                        profile=profile,
                        candidate_asins=candidate_asins,
                        item_titles=item_titles,
                    )
                    started = time.perf_counter()
                    fallback_response = client.chat_completion(
                        model=llm_config.model,
                        messages=fallback_messages,
                        temperature=0.0,
                        max_tokens=512,
                        seed=42,
                        response_format=pure_recommender_rankmap_response_format(len(candidate_asins)),
                    )
                    new_calls += 1
                    fallback_latency = time.perf_counter() - started
                    fallback_raw = fallback_response.content
                    ranking, _ = parse_candidate_rankmap(fallback_raw, candidate_asins)
                    protocol_used = "rankmap_fallback"

                rank = target_rank(ranking, target_asin)
                ndcg = ndcg_at_ks_from_rank(rank)
                row: dict[str, object] = {
                    "status": "ok",
                    "run_version": RUN_VERSION,
                    "session_id": session_id,
                    "user_id": str(session["user_id"]),
                    "target_position": int(session["target_position"]),
                    "profile_state_task_id": state.get("task_id"),
                    "profile_fallback_used": bool(state.get("fallback_used") is True),
                    "history_length": len(history),
                    "protocol_used": protocol_used,
                    "direct_validation_error": direct_error,
                    "target_rank": rank,
                    "ndcg": {str(k): value for k, value in ndcg.items()},
                    "ranking": ranking,
                    "direct_finish_reason": _finish_reason(direct_response.raw),
                    "fallback_finish_reason": (
                        _finish_reason(fallback_response.raw)
                        if fallback_response is not None
                        else None
                    ),
                    "direct_latency_seconds": direct_latency,
                    "fallback_latency_seconds": fallback_latency,
                    "session_latency_seconds": time.perf_counter() - session_started,
                    "direct_usage": _usage_dict(direct_response),
                    "fallback_usage": (
                        _usage_dict(fallback_response)
                        if fallback_response is not None
                        else None
                    ),
                }
                _append_jsonl(results_path, row)
                latest[session_id] = row
                new_successes += 1
                print(f"[{ordinal:03d}/{len(sessions):03d}] {session_id}: OK protocol={protocol_used}")
            except Exception as exc:
                row = {
                    "status": "error",
                    "run_version": RUN_VERSION,
                    "session_id": session_id,
                    "user_id": str(session.get("user_id", "")),
                    "error": str(exc),
                    "protocol_used": protocol_used,
                    "direct_validation_error": direct_error,
                    "direct_raw_response": direct_raw,
                    "fallback_raw_response": fallback_raw,
                    "session_latency_seconds": time.perf_counter() - session_started,
                }
                _append_jsonl(results_path, row)
                latest[session_id] = row
                failures_this_run.append(row)
                print(f"[{ordinal:03d}/{len(sessions):03d}] {session_id}: ERROR: {exc}")
                if config.experiment.fail_fast:
                    break

        ok_rows = [row for row in latest.values() if row.get("status") == "ok"]
        bad_rows = [row for row in latest.values() if row.get("status") != "ok"]
        ranks_by_user: dict[str, list[int]] = defaultdict(list)
        direct_successes = fallback_successes = 0
        profile_fallback_sessions = 0
        prompt_tokens = completion_tokens = total_tokens = request_count = 0
        session_latencies: list[float] = []
        max_prompt_tokens = 0

        for row in ok_rows:
            ranks_by_user[str(row["user_id"])].append(int(row["target_rank"]))
            if row.get("protocol_used") == "direct_primary":
                direct_successes += 1
            elif row.get("protocol_used") == "rankmap_fallback":
                fallback_successes += 1
            if row.get("profile_fallback_used") is True:
                profile_fallback_sessions += 1
            for usage_name in ("direct_usage", "fallback_usage"):
                usage = row.get(usage_name)
                if isinstance(usage, Mapping):
                    pt = int(usage.get("prompt_tokens", 0) or 0)
                    prompt_tokens += pt
                    completion_tokens += int(usage.get("completion_tokens", 0) or 0)
                    total_tokens += int(usage.get("total_tokens", 0) or 0)
                    request_count += 1
                    max_prompt_tokens = max(max_prompt_tokens, pt)
            latency = row.get("session_latency_seconds")
            if isinstance(latency, (int, float)):
                session_latencies.append(float(latency))

        metrics = (
            aggregate_user_ndcg(ranks_by_user)
            if ranks_by_user
            else {1: 0.0, 5: 0.0, 10: 0.0, 20: 0.0}
        )
        status = (
            "PASS"
            if len(ok_rows) == EXPECTED_SESSIONS
            and len(bad_rows) == 0
            and len(ranks_by_user) == EXPECTED_USERS
            else "INCOMPLETE"
        )
        summary: dict[str, object] = {
            "component": "PURE Recommender",
            "experiment": EXPERIMENT,
            "run_version": RUN_VERSION,
            "status": status,
            "model": llm_config.model,
            "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
            "successful_sessions": len(ok_rows),
            "failed_sessions": len(bad_rows),
            "users_in_successful_sessions": len(ranks_by_user),
            "profile_state_alignment": "target_position_minus_one",
            "sessions_using_profile_fallback_state": profile_fallback_sessions,
            "ndcg": {str(k): value for k, value in metrics.items()},
            "protocol_counts": {
                "direct_primary_successes": direct_successes,
                "fallback_successes": fallback_successes,
            },
            "usage_totals_all_requests": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "request_count": request_count,
                "max_prompt_tokens": max_prompt_tokens,
            },
            "latency": {
                "total_session_seconds": sum(session_latencies),
                "mean_session_seconds": statistics.mean(session_latencies) if session_latencies else 0.0,
                "median_session_seconds": statistics.median(session_latencies) if session_latencies else 0.0,
            },
            "generation": {"temperature": 0.0, "max_tokens": 512, "seed": 42},
            "runtime_max_concurrent_predictions": 1,
            "phase9_freeze": freeze,
            "resume": {
                "successful_sessions_at_start": successful_at_start,
                "new_successes_this_invocation": new_successes,
                "new_llm_calls_this_invocation": new_calls,
            },
            "effectiveness_handoff_policy": "aggregate_ndcg_withheld_until_phase10c",
        }
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

        handoff_summary = {key: value for key, value in summary.items() if key != "ndcg"}
        payload = {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "confirmatory_effectiveness_metrics_inspected": False,
            "summary": handoff_summary,
            "errors": [
                {
                    "session_id": row.get("session_id"),
                    "user_id": row.get("user_id"),
                    "error": row.get("error"),
                }
                for row in bad_rows
            ],
        }
        _publish(
            payload,
            "handoff: phase10 confirmatory PURE " + ("pass operational" if status == "PASS" else "incomplete"),
        )
        return 0 if status == "PASS" else 1

    except Exception as exc:
        payload = {
            "state": "ERROR",
            "experiment": EXPERIMENT,
            "confirmatory_effectiveness_metrics_inspected": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        _publish(payload, "handoff: phase10 confirmatory PURE error")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
