"""Run the frozen Phase 10B3 confirmatory Recency-Focused baseline.

This runner reuses the accepted Phase 6 Recency prompt and the same mechanical
hybrid output policy, but consumes the immutable 767-session Phase 9 cohort.
It is resumable at session level and deliberately keeps aggregate effectiveness
metrics out of the Git handoff until PURE has also completed.
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

EXPERIMENT = "phase10_confirmatory_recency_v1"
RUN_VERSION = "confirmatory_recency_hybrid_v1"
EXPECTED_USERS = 150
EXPECTED_SESSIONS = 767
COHORT_SHA256 = "72701badc5ae325472a59846b4ba5b1dc0bc8c2351d181a607ae7b7fa87aebca"
SESSIONS_SHA256 = "0d00f4c4358d50608b47461df820ab09229dd75b7db3950a1cb369f309c6e859"
CONFIG_PATH = REPO_ROOT / "config" / "phase10_confirmatory_recency.toml"
COHORT_USERS_PATH = REPO_ROOT / "outputs/phase9_confirmatory_cohort_v1/cohort_users.json"
COHORT_SUMMARY_PATH = REPO_ROOT / "outputs/phase9_confirmatory_cohort_v1/cohort_summary.json"
PROFILE_SUMMARY_PATH = REPO_ROOT / "outputs/phase10_confirmatory_profile_updater_v2/summary.json"


def _append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _load_latest_results(path: Path) -> dict[str, dict[str, object]]:
    """Load the latest audit row per frozen session for safe resume."""

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
            session_id = row.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise RuntimeError(f"Missing session_id at {path}:{line_number}")
            marker = row.get("run_version")
            if marker != RUN_VERSION:
                raise RuntimeError(
                    f"Mixed-protocol result artifact detected at {path}:{line_number}: {marker!r}"
                )
            latest[session_id] = row
    return latest


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return value


def _publish(payload: dict[str, object], message: str) -> None:
    ok, detail = publish_handoff(REPO_ROOT, payload, commit_message=message, auto_push=True)
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {detail}")


def _preflight(config) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Verify the prospective cohort and the completed upstream profile stage."""

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
    if len({str(row['user_id']) for row in sessions}) != EXPECTED_USERS:
        raise RuntimeError("Frozen confirmatory session user count mismatch")

    # Recency itself does not consume PURE profiles, but stage ordering is frozen:
    # recommender evaluation begins only after the final profile artifact is PASS.
    profile_summary = _load_json(PROFILE_SUMMARY_PATH)
    if profile_summary.get("status") != "PASS":
        raise RuntimeError("Phase 10B2 final Profile Updater summary is not PASS")
    if int(profile_summary.get("successful_updates", -1)) != 1067:
        raise RuntimeError("Phase 10B2 final Profile Updater count mismatch")
    if int(profile_summary.get("failed_updates", -1)) != 0:
        raise RuntimeError("Phase 10B2 final Profile Updater contains unresolved failures")
    return freeze, sessions


def main() -> int:
    try:
        config = load_phase2_config(CONFIG_PATH)
        llm_config = load_local_llm_config(REPO_ROOT / "config/local_llm.toml")
        freeze, sessions = _preflight(config)

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
        successful_at_start = sum(row.get("status") == "ok" for row in latest.values())

        print("=" * 104)
        print("PHASE 10B3 — CONFIRMATORY RECENCY-FOCUSED / HYBRID OUTPUT")
        print("=" * 104)
        print(f"Frozen sessions             : {len(sessions)}")
        print(f"Frozen users                : {EXPECTED_USERS}")
        print(f"Existing successful sessions: {successful_at_start}")
        print("Runtime concurrency          : 1")
        print("Temperature / seed / max     : 0.0 / 42 / 512")
        print("Effectiveness handoff        : BLINDED until PURE completion")
        print()

        new_calls = 0
        new_successes = 0
        failures: list[dict[str, object]] = []

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
                history, candidate_asins, target_asin = shared._validate_session(
                    session, histories, item_titles
                )
                direct_messages = build_recency_messages(
                    history=history,
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
                    fallback_messages = build_recency_rankmap_messages(
                        history=history,
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
                    "history_length": len(history),
                    "protocol_used": protocol_used,
                    "direct_validation_error": direct_error,
                    "target_rank": rank,
                    "ndcg": {str(k): value for k, value in ndcg.items()},
                    "ranking": ranking,
                    "direct_finish_reason": shared._finish_reason(direct_response.raw),
                    "fallback_finish_reason": (
                        shared._finish_reason(fallback_response.raw)
                        if fallback_response is not None
                        else None
                    ),
                    "direct_latency_seconds": direct_latency,
                    "fallback_latency_seconds": fallback_latency,
                    "session_latency_seconds": time.perf_counter() - session_started,
                    "direct_usage": shared._usage_dict(direct_response),
                    "fallback_usage": (
                        shared._usage_dict(fallback_response)
                        if fallback_response is not None
                        else None
                    ),
                }
                _append_jsonl(results_path, row)
                latest[session_id] = row
                new_successes += 1
                print(
                    f"[{ordinal:03d}/{len(sessions):03d}] {session_id}: "
                    f"OK protocol={protocol_used}"
                )
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
                failures.append(row)
                print(f"[{ordinal:03d}/{len(sessions):03d}] {session_id}: ERROR: {exc}")
                if config.experiment.fail_fast:
                    break

        ok_rows = [row for row in latest.values() if row.get("status") == "ok"]
        bad_rows = [row for row in latest.values() if row.get("status") != "ok"]
        ranks_by_user: dict[str, list[int]] = defaultdict(list)
        direct_successes = fallback_successes = 0
        prompt_tokens = completion_tokens = total_tokens = request_count = 0
        latencies: list[float] = []

        for row in ok_rows:
            ranks_by_user[str(row["user_id"])].append(int(row["target_rank"]))
            if row.get("protocol_used") == "direct_primary":
                direct_successes += 1
            elif row.get("protocol_used") == "rankmap_fallback":
                fallback_successes += 1
            for usage_name in ("direct_usage", "fallback_usage"):
                usage = row.get(usage_name)
                if isinstance(usage, Mapping):
                    prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                    completion_tokens += int(usage.get("completion_tokens", 0) or 0)
                    total_tokens += int(usage.get("total_tokens", 0) or 0)
                    request_count += 1
            value = row.get("session_latency_seconds")
            if isinstance(value, (int, float)):
                latencies.append(float(value))

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
            "baseline": "Recency-Focused",
            "experiment": EXPERIMENT,
            "run_version": RUN_VERSION,
            "status": status,
            "model": llm_config.model,
            "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
            "successful_sessions": len(ok_rows),
            "failed_sessions": len(bad_rows),
            "users_in_successful_sessions": len(ranks_by_user),
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
            },
            "latency": {
                "total_session_seconds": sum(latencies),
                "mean_session_seconds": statistics.mean(latencies) if latencies else 0.0,
                "median_session_seconds": statistics.median(latencies) if latencies else 0.0,
            },
            "generation": {"temperature": 0.0, "max_tokens": 512, "seed": 42},
            "runtime_max_concurrent_predictions": 1,
            "phase9_freeze": freeze,
            "resume": {
                "successful_sessions_at_start": successful_at_start,
                "new_successes_this_invocation": new_successes,
                "new_llm_calls_this_invocation": new_calls,
            },
            "effectiveness_handoff_policy": "aggregate_ndcg_withheld_until_both_primary_methods_complete",
        }
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

        # Deliberately exclude aggregate NDCG from the Git handoff. The local
        # summary keeps it for Phase 10C after PURE completes.
        handoff_summary = {
            key: value
            for key, value in summary.items()
            if key != "ndcg"
        }
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
                for row in bad_rows[:10]
            ],
        }
        _publish(
            payload,
            "handoff: phase10 confirmatory Recency "
            + ("pass operational" if status == "PASS" else "incomplete"),
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
        _publish(payload, "handoff: phase10 confirmatory Recency error")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
