"""NDCG metrics for one-relevant-item candidate ranking."""

from __future__ import annotations

from collections import defaultdict
import math
from statistics import mean
from typing import Iterable, Mapping


def ndcg_at_k_from_rank(rank: int, k: int) -> float:
    """Compute NDCG@k when the candidate set has exactly one relevant item."""
    if rank < 1:
        raise ValueError("rank must be >= 1")
    if k < 1:
        raise ValueError("k must be >= 1")
    if rank > k:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def ndcg_at_ks_from_rank(rank: int, ks: Iterable[int] = (1, 5, 10, 20)) -> dict[int, float]:
    return {k: ndcg_at_k_from_rank(rank, k) for k in ks}


def aggregate_user_ndcg(
    session_ranks: Mapping[str, Iterable[int]],
    ks: Iterable[int] = (1, 5, 10, 20),
) -> dict[int, float]:
    """Average sessions within each user first, then average across users."""
    ks = tuple(ks)
    per_k_user_means: dict[int, list[float]] = defaultdict(list)

    for ranks_iter in session_ranks.values():
        ranks = list(ranks_iter)
        if not ranks:
            continue
        for k in ks:
            per_k_user_means[k].append(mean(ndcg_at_k_from_rank(rank, k) for rank in ranks))

    return {
        k: (mean(per_k_user_means[k]) if per_k_user_means[k] else 0.0)
        for k in ks
    }
