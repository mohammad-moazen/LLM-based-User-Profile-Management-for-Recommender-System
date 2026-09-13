"""Freeze the Phase 9 NEW-user confirmatory cohort. Zero LLM calls."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import tomllib
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.analysis.confirmatory_cohort import (
    build_confirmatory_sessions,
    canonical_sha256,
    cohort_user_records,
    select_new_confirmatory_users,
    validate_confirmatory_sessions,
)
from pure_recommender.experiment_handoff import publish_handoff
from pure_recommender.phase2 import load_histories, load_items, load_sessions

EXPERIMENT = "phase9_confirmatory_cohort_design_v1"
CONFIG_PATH = REPO_ROOT / "config" / "phase9_confirmatory_cohort.toml"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _write_jsonl_gz(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _rate(reference: Mapping[str, object], section_name: str, numerator: str, denominator: str) -> float:
    section = reference.get(section_name)
    if not isinstance(section, Mapping):
        raise ValueError(f"Missing reference section: {section_name}")
    return float(section[numerator]) / float(section[denominator])


def main() -> int:
    with CONFIG_PATH.open("rb") as handle:
        cfg = tomllib.load(handle)
    inp = cfg["input"]
    cohort = cfg["cohort"]
    confirmatory = cfg["confirmatory"]
    reference = cfg["reference"]
    output_dir = _resolve(str(cfg["output"]["directory"]))
    output_dir.mkdir(parents=True, exist_ok=True)

    items_path = _resolve(str(inp["items_path"]))
    interactions_path = _resolve(str(inp["interactions_path"]))
    pilot_sessions_path = _resolve(str(inp["pilot_sessions_path"]))
    for path in (items_path, interactions_path, pilot_sessions_path):
        if not path.exists():
            raise FileNotFoundError(path)

    new_users = int(cohort["new_users"])
    min_history = int(cohort["min_history"])
    selection_seed = int(cohort["user_selection_seed"])
    candidate_size = int(cohort["candidate_size"])
    candidate_seed = int(cohort["candidate_seed"])
    expected_pilot_users = int(cohort["expected_pilot_users"])

    item_titles = load_items(items_path)
    histories = load_histories(interactions_path)
    pilot_sessions = load_sessions(pilot_sessions_path)
    pilot_users = {str(row["user_id"]) for row in pilot_sessions}

    selected_users, ordered_eligible = select_new_confirmatory_users(
        histories,
        pilot_user_ids=pilot_users,
        expected_pilot_users=expected_pilot_users,
        new_users=new_users,
        min_history=min_history,
        selection_seed=selection_seed,
    )
    sessions = build_confirmatory_sessions(
        histories,
        item_universe=item_titles.keys(),
        selected_users=selected_users,
        min_history=min_history,
        candidate_size=candidate_size,
        candidate_seed=candidate_seed,
    )
    validate_confirmatory_sessions(
        sessions,
        histories,
        selected_users=selected_users,
        min_history=min_history,
        candidate_size=candidate_size,
    )
    users = cohort_user_records(selected_users, ordered_eligible, histories, min_history=min_history)

    session_count = len(sessions)
    profile_events = sum(int(row["profile_evidence_events"]) for row in users)
    history_lengths = [int(row["history_length"]) for row in users]
    cohort_hash = canonical_sha256(users)
    sessions_hash = canonical_sha256(sessions)

    review_tokens = _rate(reference, "review_extractor", "total_tokens", "requests")
    review_seconds = _rate(reference, "review_extractor", "latency_seconds", "requests")
    updater_tokens = _rate(reference, "profile_updater", "total_tokens", "requests")
    updater_seconds = _rate(reference, "profile_updater", "latency_seconds", "requests")
    pure_tokens = _rate(reference, "pure", "total_tokens", "sessions")
    pure_seconds = _rate(reference, "pure", "latency_seconds", "sessions")
    pure_requests = _rate(reference, "pure", "requests", "sessions")
    rec_tokens = _rate(reference, "recency", "total_tokens", "sessions")
    rec_seconds = _rate(reference, "recency", "latency_seconds", "sessions")
    rec_requests = _rate(reference, "recency", "requests", "sessions")
    seq_tokens = _rate(reference, "sequential", "total_tokens", "sessions")
    seq_seconds = _rate(reference, "sequential", "latency_seconds", "sessions")
    seq_requests = _rate(reference, "sequential", "requests", "sessions")
    icl_tokens = _rate(reference, "icl", "total_tokens", "sessions")
    icl_seconds = _rate(reference, "icl", "latency_seconds", "sessions")
    icl_requests = _rate(reference, "icl", "requests", "sessions")

    primary_requests = 2 * profile_events + session_count * (pure_requests + rec_requests)
    primary_tokens = profile_events * (review_tokens + updater_tokens) + session_count * (pure_tokens + rec_tokens)
    primary_seconds = profile_events * (review_seconds + updater_seconds) + session_count * (pure_seconds + rec_seconds)
    optional_requests = session_count * (seq_requests + icl_requests)
    optional_tokens = session_count * (seq_tokens + icl_tokens)
    optional_seconds = session_count * (seq_seconds + icl_seconds)

    cost_estimate = {
        "interpretation": "empirical_reference_estimate_not_runtime_guarantee",
        "monetary_api_cost": "not_applicable_local_inference",
        "primary_confirmatory_scope": {
            "methods": ["PURE", "Recency-Focused"],
            "estimated_llm_requests": primary_requests,
            "estimated_total_tokens": primary_tokens,
            "estimated_inference_hours": primary_seconds / 3600.0,
        },
        "optional_secondary_methods": {
            "methods": ["Sequential", "ICL"],
            "additional_estimated_llm_requests": optional_requests,
            "additional_estimated_total_tokens": optional_tokens,
            "additional_estimated_inference_hours": optional_seconds / 3600.0,
        },
        "full_four_method_scope": {
            "estimated_llm_requests": primary_requests + optional_requests,
            "estimated_total_tokens": primary_tokens + optional_tokens,
            "estimated_inference_hours": (primary_seconds + optional_seconds) / 3600.0,
        },
    }

    summary = {
        "experiment": EXPERIMENT,
        "status": "PASS",
        "llm_calls": 0,
        "new_users": new_users,
        "pilot_users_excluded": len(pilot_users),
        "pilot_overlap": 0,
        "eligible_users_total": len(ordered_eligible),
        "first_new_user_eligible_rank": int(users[0]["deterministic_eligible_rank"]),
        "last_new_user_eligible_rank": int(users[-1]["deterministic_eligible_rank"]),
        "recommendation_sessions": session_count,
        "profile_evidence_events": profile_events,
        "history_length": {
            "min": min(history_lengths),
            "max": max(history_lengths),
            "mean": sum(history_lengths) / len(history_lengths),
        },
        "candidate_size": candidate_size,
        "candidate_seed": candidate_seed,
        "user_selection_seed": selection_seed,
        "cohort_manifest_sha256": cohort_hash,
        "sessions_sha256": sessions_hash,
        "primary_endpoint": {
            "method": str(confirmatory["primary_method"]),
            "baseline": str(confirmatory["primary_baseline"]),
            "metric": str(confirmatory["primary_metric"]),
            "alpha": float(confirmatory["alpha"]),
            "two_sided": bool(confirmatory["two_sided"]),
            "target_power": float(confirmatory["target_power"]),
        },
        "cost_estimate": cost_estimate,
    }

    (output_dir / "cohort_users.json").write_text(json.dumps(users, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_jsonl_gz(output_dir / "sessions.jsonl.gz", sessions)
    (output_dir / "cost_estimate.json").write_text(json.dumps(cost_estimate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "cohort_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = (
        "# Phase 9 — Confirmatory new-user cohort design\n\n"
        "**PASS — design only / zero LLM calls**\n\n"
        f"- New users: **{new_users}**\n"
        f"- Pilot users excluded: **{len(pilot_users)}**\n"
        f"- Deterministic eligible ranks: **{users[0]['deterministic_eligible_rank']}..{users[-1]['deterministic_eligible_rank']}**\n"
        f"- Recommendation sessions: **{session_count}**\n"
        f"- Review Extractor events: **{profile_events}**\n"
        f"- Profile Updater events: **{profile_events}**\n"
        f"- Primary endpoint: **PURE vs Recency-Focused / {confirmatory['primary_metric']}**\n"
        f"- Cohort SHA256: `{cohort_hash}`\n"
        f"- Sessions SHA256: `{sessions_hash}`\n\n"
        "## Compute planning\n\n"
        f"- Primary PURE+Recency estimated requests: **{primary_requests:.1f}**\n"
        f"- Primary estimated tokens: **{primary_tokens:,.0f}**\n"
        f"- Primary estimated inference time: **{primary_seconds / 3600.0:.2f} h**\n"
        f"- Optional Sequential+ICL extra time: **{optional_seconds / 3600.0:.2f} h**\n"
        f"- Full four-method estimated time: **{(primary_seconds + optional_seconds) / 3600.0:.2f} h**\n\n"
        "These are empirical planning estimates from the frozen 20-user runs, not guarantees. "
        "The next execution stage must consume these frozen users/sessions without reselection.\n"
    )
    (output_dir / "phase9_report.md").write_text(report, encoding="utf-8")

    ok, message = publish_handoff(
        REPO_ROOT,
        {
            "state": "RESULT",
            "experiment": EXPERIMENT,
            "summary": summary,
            "recommended_uploads_if_detailed_review_is_needed": [
                str((output_dir / "cohort_summary.json").relative_to(REPO_ROOT)),
                str((output_dir / "cost_estimate.json").relative_to(REPO_ROOT)),
                str((output_dir / "phase9_report.md").relative_to(REPO_ROOT)),
            ],
        },
        commit_message="handoff: phase9 confirmatory cohort design",
        auto_push=True,
    )
    print(f"{'HANDOFF' if ok else 'HANDOFF WARNING'}: {message}")
    print(f"new_users               : {new_users}")
    print(f"recommendation_sessions : {session_count}")
    print(f"profile_evidence_events : {profile_events}")
    print(f"cohort_sha256           : {cohort_hash}")
    print(f"sessions_sha256         : {sessions_hash}")
    print(f"primary_estimated_hours : {primary_seconds / 3600.0:.2f}")
    print("status                  : PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
