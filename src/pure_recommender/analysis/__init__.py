"""Deterministic post-hoc analysis utilities for frozen experiment results."""

from .final_results import (
    NDCG_KS,
    METHOD_ORDER,
    bootstrap_paired_user_delta,
    compute_per_user_ndcg,
    compute_rank_summary,
    compute_win_tie_loss,
    load_json,
    load_jsonl_rows,
    relative_improvement_percent,
    validate_aligned_results,
    write_grouped_ndcg_svg,
)

__all__ = [
    "NDCG_KS",
    "METHOD_ORDER",
    "bootstrap_paired_user_delta",
    "compute_per_user_ndcg",
    "compute_rank_summary",
    "compute_win_tie_loss",
    "load_json",
    "load_jsonl_rows",
    "relative_improvement_percent",
    "validate_aligned_results",
    "write_grouped_ndcg_svg",
]
