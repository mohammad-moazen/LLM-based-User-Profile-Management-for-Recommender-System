"""Final summary builder for Phase 10B2 recovery."""

from __future__ import annotations

import json
from typing import Any

from pure_recommender.phase10_profile_resume import aggregate_latest_states
from pure_recommender.phase10_profile_resume_context import EXPECTED_UPDATES, EXPECTED_USERS, MAX_RECOVERY_ATTEMPTS


def finalize_resume(ctx: dict[str, Any], *, new_successes: int, new_calls: int) -> dict[str, object]:
    aggregate = aggregate_latest_states(ctx["latest"])
    status = "PASS" if aggregate["successful_updates"] == EXPECTED_UPDATES and aggregate["failed_updates"] == 0 else "INCOMPLETE"
    summary = {
        "component": "Profile Updater",
        "run_version": "confirmatory_resume_v1",
        "status": status,
        "model": ctx["llm_cfg"].model,
        "model_alignment": "derivative_local_model_not_exact_paper_checkpoint",
        "users": EXPECTED_USERS,
        "expected_updates": EXPECTED_UPDATES,
        **aggregate,
        "generation": {"temperature": 0.0, "max_tokens": 1024, "seed": 42},
        "validation": "same_category_id_selection_plus_information_preserving_dominance_guard",
        "recovery": {
            "response_repair": "none",
            "reused_successes_at_start": ctx["ok_at_start"],
            "new_successes": new_successes,
            "new_llm_calls": new_calls,
            "max_fresh_attempts_per_task": MAX_RECOVERY_ATTEMPTS,
            "introduced_before_confirmatory_recommendation_outcomes": True,
        },
        "state_artifact": str(ctx["states_path"]),
        "phase9_freeze": ctx["freeze"],
    }
    ctx["summary_path"].write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


__all__ = ["finalize_resume"]
