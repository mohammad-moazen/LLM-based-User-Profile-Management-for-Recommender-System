"""Diagnose the two malformed rankings from Phase 5 full attempt 1.

This diagnostic does NOT edit or resume the final Phase 5 result artifact. It reads
only the failed local rows from ``outputs/phase5_pure_recommender_final/results.jsonl``
and tests a formatting-only corrective retry. The retry preserves the same frozen
history, profile state, candidate set, model, temperature, seed, and output schema.
The previous invalid model response is included in the conversation and the model
is asked only to correct the permutation format.

If this diagnostic succeeds, the production runner can adopt a bounded retry-on-
format-error policy and then rerun all 94 sessions cleanly under one homogeneous
protocol. No malformed ranking is repaired deterministically after generation.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
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
from pure_recommender.evaluation.metrics import ndcg_at_ks_from_rank
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.llm import OpenAICompatibleLLMClient, load_local_llm_config
from pure_recommender.phase2 import load_histories, load_items, load_sessions
from pure_recommender.phase5 import load_phase5_config
from pure_recommender.pure import (
    build_pure_recommender_messages,
    profile_from_mapping,
    pure_recommender_response_format,
)
import run_phase5_pure_recommender as shared_runner


EXPERIMENT = "phase5_malformed_ranking_retry_diagnostic"
CONFIG_PATH = REPO_ROOT / "config" / "phase5_pure_recommender_full.toml"
RESULTS_PATH = REPO_ROOT / "outputs" / "phase5_pure_recommender_final" / "results.jsonl"


def _load_latest_results(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(
            "Phase 5 full-attempt results were not found. Run the full attempt before this diagnostic: "
            f"{path}"
        )

    latest: dict[str, dict[str, object]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                continue
            session_id = row.get("session_id")
            if isinstance(session_id, str) and session_id:
                latest[session_id] = row
    return latest


def _ranking_problem(raw_response: str, candidate_count: int) -> dict[str, object]:
    """Describe duplicates/missing numbers for audit only; never repair the ranking."""

    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError:
        return {"json_valid": False}

    ranking = payload.get("ranking") if isinstance(payload, dict) else None
    if not isinstance(ranking, list):
        return {"json_valid": True, "ranking_is_array": False}

    normalized: list[int] = []
    for value in ranking:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            normalized.append(value)
        elif isinstance(value, str) and value.strip().isdigit():
            normalized.append(int(value.strip()))

    counts = Counter(normalized)
    duplicates = sorted(number for number, count in counts.items() if count > 1)
    expected = set(range(1, candidate_count + 1))
    missing = sorted(expected - set(normalized))
    unexpected = sorted(set(normalized) - expected)
    return {
        "json_valid": True,
        "ranking_is_array": True,
        "ranking_length": len(ranking),
        "duplicates": duplicates,
        "missing": missing,
        "unexpected": unexpected,
    }


def _finish_reason(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    value = choices[0].get("finish_reason")
    return value if isinstance(value, str) else None


def main() -> int:
    config = load_phase5_config(CONFIG_PATH)
    llm_config = load_local_llm_config(REPO_ROOT / "config" / "local_llm.toml")

    latest = _load_latest_results(RESULTS_PATH)
    failed_rows = [row for row in latest.values() if row.get("status") != "ok"]
    failed_rows.sort(key=lambda row: str(row.get("session_id", "")))
    if not failed_rows:
        raise RuntimeError("No failed Phase 5 rows were found; nothing to diagnose")

    item_titles = load_items(config.input.items_path)
    histories = load_histories(config.input.interactions_path)
    all_sessions = load_sessions(config.input.sessions_path)
    sessions_by_id = {str(row["session_id"]): row for row in all_sessions}
    profile_states = shared_runner._load_profile_states(config.input.profile_states_path)

    client = OpenAICompatibleLLMClient(
        base_url=llm_config.base_url,
        timeout_seconds=llm_config.timeout_seconds,
    )
    visible_models = client.list_models()
    if llm_config.model not in visible_models:
        raise RuntimeError(
            f"Configured model {llm_config.model!r} is not exposed by local server; visible={visible_models}"
        )

    rows: list[dict[str, object]] = []
    print("=" * 96)
    print("PHASE 5 — MALFORMED RANKING CORRECTIVE-RETRY DIAGNOSTIC")
    print("=" * 96)
    print(f"Failed rows found      : {len(failed_rows)}")
    print(f"Model                  : {llm_config.model}")
    print(f"Temperature            : {config.generation.temperature}")
    print(f"Seed                   : {config.generation.seed}")
    print(f"Max output tokens      : {config.generation.max_tokens}")
    print("Deterministic repair    : NONE")
    print()

    for ordinal, failed in enumerate(failed_rows, start=1):
        session_id = str(failed.get("session_id", ""))
        if session_id not in sessions_by_id:
            raise RuntimeError(f"Failed session {session_id!r} is absent from frozen sessions")

        invalid_response = str(failed.get("raw_response") or "").strip()
        if not invalid_response:
            raise RuntimeError(f"Failed session {session_id!r} has no raw response to correct")

        session = sessions_by_id[session_id]
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

        # Confirm that the stored first attempt is truly invalid under the frozen parser.
        first_error: str | None = None
        try:
            parse_complete_ranking(invalid_response, candidate_asins)
        except Exception as exc:  # expected diagnostic path
            first_error = str(exc)
        if first_error is None:
            raise RuntimeError(
                f"Stored first response for {session_id} is valid under the current parser; diagnostic mismatch"
            )

        messages = build_pure_recommender_messages(
            history=history,
            profile=profile,
            candidate_asins=candidate_asins,
            item_titles=item_titles,
        )
        problem = _ranking_problem(invalid_response, len(candidate_asins))
        corrective_instruction = (
            "Your previous JSON ranking is structurally invalid because it is not a complete unique "
            "permutation of the numbered candidates. Correct ONLY the output format. Do not add an "
            "explanation and do not change the recommendation task or use any new information. "
            f"Return exactly one JSON object whose `ranking` contains every integer from 1 through "
            f"{len(candidate_asins)} exactly once, with no duplicates and no omissions."
        )
        retry_messages = messages + [
            {"role": "assistant", "content": invalid_response},
            {"role": "user", "content": corrective_instruction},
        ]

        raw_retry = ""
        started = time.perf_counter()
        try:
            response = client.chat_completion(
                model=llm_config.model,
                messages=retry_messages,
                temperature=config.generation.temperature,
                max_tokens=config.generation.max_tokens,
                seed=config.generation.seed,
                response_format=pure_recommender_response_format(len(candidate_asins)),
            )
            elapsed = time.perf_counter() - started
            raw_retry = response.content
            ranking = parse_complete_ranking(raw_retry, candidate_asins)
            rank = target_rank(ranking, target_asin)
            ndcg = ndcg_at_ks_from_rank(rank)
            usage = dict(response.usage) if response.usage else {}
            result: dict[str, object] = {
                "status": "ok",
                "session_id": session_id,
                "first_attempt_error": first_error,
                "first_attempt_problem": problem,
                "retry_target_rank": rank,
                "retry_ndcg": {str(k): value for k, value in ndcg.items()},
                "retry_finish_reason": _finish_reason(response.raw),
                "retry_latency_seconds": elapsed,
                "retry_usage": usage,
            }
            rows.append(result)
            print(
                f"[{ordinal}/{len(failed_rows)}] {session_id}: RETRY PASS; "
                f"target_rank={rank}; latency={elapsed:.2f}s"
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            result = {
                "status": "error",
                "session_id": session_id,
                "first_attempt_error": first_error,
                "first_attempt_problem": problem,
                "retry_error": str(exc),
                "retry_raw_response": raw_retry,
                "retry_latency_seconds": elapsed,
            }
            rows.append(result)
            print(f"[{ordinal}/{len(failed_rows)}] {session_id}: RETRY ERROR: {exc}")

    success_count = sum(1 for row in rows if row.get("status") == "ok")
    status = "PASS" if success_count == len(rows) else "INCOMPLETE"
    payload = {
        "state": "RESULT",
        "experiment": EXPERIMENT,
        "summary": {
            "failed_rows_tested": len(rows),
            "successful_corrective_retries": success_count,
            "failed_corrective_retries": len(rows) - success_count,
            "generation": {
                "temperature": config.generation.temperature,
                "max_tokens": config.generation.max_tokens,
                "seed": config.generation.seed,
                "structured_output": "same_phase5_complete_numbered_candidate_ranking_json_schema",
            },
            "retry_policy_tested": "one_formatting_only_corrective_retry_after_strict_parser_failure",
            "deterministic_post_generation_repair": False,
            "status": status,
        },
        "rows": rows,
    }
    ok, message = publish_handoff(
        REPO_ROOT,
        payload,
        commit_message=f"handoff: phase5 malformed ranking retry diagnostic {status.lower()}",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
    print()
    print(f"status: {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
