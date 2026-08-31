"""
evaluation/metrics/retrieval_metrics.py
========================================
Retrieval quality metrics for VisionRAG-X.

All functions operate on lists of string IDs.  IDs can represent any
retrievable unit (chunk_id, frame_id, page_id, etc.) as long as they
are consistent between the retrieved list and the relevance judgements.

Implemented metrics
-------------------
- recall_at_k
- precision_at_k
- mrr  (Mean Reciprocal Rank — single-query variant)
- ndcg_at_k
- average_precision

Batch wrappers (return the mean over a list of queries)
-------------------------------------------------------
- batch_recall_at_k
- batch_precision_at_k
- batch_mrr
- batch_ndcg_at_k

Usage
-----
    from evaluation.metrics.retrieval_metrics import (
        recall_at_k,
        batch_ndcg_at_k,
    )

    retrieved = ["c1", "c3", "c5", "c2", "c4"]
    relevant  = {"c1", "c3"}

    r = recall_at_k(retrieved, relevant, k=3)
    # 0.5  — only c1 found in top 3 out of {c1, c3}
"""

from __future__ import annotations

import math
from typing import List, Sequence, Set, Union


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
RetrievedList = Sequence[str]
RelevantSet   = Union[Sequence[str], Set[str]]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_set(ids: RelevantSet) -> Set[str]:
    """Convert a sequence or set of IDs to a Python set."""
    return ids if isinstance(ids, set) else set(ids)


def _safe_mean(values: List[float]) -> float:
    """Return the mean of a non-empty list, or 0.0 for an empty list."""
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# Single-query metrics
# ---------------------------------------------------------------------------

def recall_at_k(
    retrieved_ids: RetrievedList,
    relevant_ids: RelevantSet,
    k: int,
) -> float:
    """
    Compute Recall@K for a single query.

    Recall@K = |relevant ∩ retrieved[:K]| / |relevant|

    Parameters
    ----------
    retrieved_ids : sequence of str
        Ordered list of retrieved chunk/document IDs (most relevant first).
    relevant_ids : sequence or set of str
        Ground-truth relevant IDs for this query.
    k : int
        Cut-off rank.

    Returns
    -------
    float
        Recall@K in [0.0, 1.0].  Returns 0.0 if ``relevant_ids`` is empty.

    Examples
    --------
    >>> recall_at_k(["a", "b", "c", "d"], ["a", "c", "e"], k=3)
    0.6666666666666666
    """
    if k <= 0:
        raise ValueError(f"k must be a positive integer, got {k}")

    relevant_set = _to_set(relevant_ids)
    if not relevant_set:
        return 0.0

    top_k = set(retrieved_ids[:k])
    hits  = len(top_k & relevant_set)
    return hits / len(relevant_set)


def precision_at_k(
    retrieved_ids: RetrievedList,
    relevant_ids: RelevantSet,
    k: int,
) -> float:
    """
    Compute Precision@K for a single query.

    Precision@K = |relevant ∩ retrieved[:K]| / K

    Parameters
    ----------
    retrieved_ids : sequence of str
        Ordered list of retrieved IDs (most relevant first).
    relevant_ids : sequence or set of str
        Ground-truth relevant IDs.
    k : int
        Cut-off rank.

    Returns
    -------
    float
        Precision@K in [0.0, 1.0].

    Examples
    --------
    >>> precision_at_k(["a", "b", "c", "d"], ["a", "c", "e"], k=3)
    0.6666666666666666
    """
    if k <= 0:
        raise ValueError(f"k must be a positive integer, got {k}")

    relevant_set = _to_set(relevant_ids)
    top_k = retrieved_ids[:k]
    hits  = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / k


def mrr(
    retrieved_ids: RetrievedList,
    relevant_ids: RelevantSet,
) -> float:
    """
    Compute the Reciprocal Rank for a single query.

    MRR (single query) = 1 / rank_of_first_relevant_result

    Returns 0.0 if no relevant document appears in the retrieved list.

    Parameters
    ----------
    retrieved_ids : sequence of str
        Ordered list of retrieved IDs (most relevant first).
    relevant_ids : sequence or set of str
        Ground-truth relevant IDs.

    Returns
    -------
    float
        Reciprocal rank in (0.0, 1.0].

    Examples
    --------
    >>> mrr(["x", "a", "b"], {"a", "c"})
    0.5
    """
    relevant_set = _to_set(relevant_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    retrieved_ids: RetrievedList,
    relevant_ids: RelevantSet,
    k: int,
) -> float:
    """
    Compute Normalised Discounted Cumulative Gain (NDCG) at rank K.

    Assumes binary relevance: gain = 1 if relevant, else 0.

    NDCG@K = DCG@K / IDCG@K

    where:
        DCG@K  = Σ_{i=1}^{K} rel_i / log2(i + 1)
        IDCG@K = DCG of the ideal ranking (all relevant docs first)

    Parameters
    ----------
    retrieved_ids : sequence of str
        Ordered list of retrieved IDs (most relevant first).
    relevant_ids : sequence or set of str
        Ground-truth relevant IDs.
    k : int
        Cut-off rank.

    Returns
    -------
    float
        NDCG@K in [0.0, 1.0].  Returns 0.0 if ``relevant_ids`` is empty.

    Examples
    --------
    >>> ndcg_at_k(["a", "b", "c", "d"], ["a", "c"], k=4)
    0.8154648767857287
    """
    if k <= 0:
        raise ValueError(f"k must be a positive integer, got {k}")

    relevant_set = _to_set(relevant_ids)
    if not relevant_set:
        return 0.0

    # Actual DCG
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k], start=1):
        if doc_id in relevant_set:
            dcg += 1.0 / math.log2(i + 1)

    # Ideal DCG (best possible ranking)
    n_ideal = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n_ideal + 1))

    return dcg / idcg if idcg > 0 else 0.0


def average_precision(
    retrieved_ids: RetrievedList,
    relevant_ids: RelevantSet,
) -> float:
    """
    Compute Average Precision (AP) for a single query.

    AP = (1 / |relevant|) * Σ_{k: retrieved[k] is relevant} Precision@k

    Returns 0.0 if ``relevant_ids`` is empty.

    Parameters
    ----------
    retrieved_ids : sequence of str
        Ordered list of retrieved IDs (most relevant first).
    relevant_ids : sequence or set of str
        Ground-truth relevant IDs.

    Returns
    -------
    float
        Average Precision in [0.0, 1.0].

    Examples
    --------
    >>> average_precision(["a", "b", "c", "d"], {"a", "c"})
    0.75
    """
    relevant_set = _to_set(relevant_ids)
    if not relevant_set:
        return 0.0

    hits = 0
    cumulative_precision = 0.0
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_set:
            hits += 1
            cumulative_precision += hits / rank

    return cumulative_precision / len(relevant_set)


# ---------------------------------------------------------------------------
# Batch wrappers — return mean over a list of queries
# ---------------------------------------------------------------------------

def batch_recall_at_k(
    list_retrieved: List[RetrievedList],
    list_relevant: List[RelevantSet],
    k: int,
) -> float:
    """
    Compute mean Recall@K over a collection of queries.

    Parameters
    ----------
    list_retrieved : list of retrieved-ID lists
        One entry per query.
    list_relevant : list of relevant-ID sets/lists
        One entry per query, in the same order as ``list_retrieved``.
    k : int
        Cut-off rank.

    Returns
    -------
    float
        Mean Recall@K in [0.0, 1.0].

    Raises
    ------
    ValueError
        If ``list_retrieved`` and ``list_relevant`` have different lengths.

    Examples
    --------
    >>> batch_recall_at_k([["a","b"],["c","d"]], [["a"],["d"]], k=2)
    1.0
    """
    if len(list_retrieved) != len(list_relevant):
        raise ValueError(
            "list_retrieved and list_relevant must have the same length. "
            f"Got {len(list_retrieved)} and {len(list_relevant)}."
        )
    scores = [
        recall_at_k(ret, rel, k)
        for ret, rel in zip(list_retrieved, list_relevant)
    ]
    return _safe_mean(scores)


def batch_precision_at_k(
    list_retrieved: List[RetrievedList],
    list_relevant: List[RelevantSet],
    k: int,
) -> float:
    """
    Compute mean Precision@K over a collection of queries.

    Parameters
    ----------
    list_retrieved : list of retrieved-ID lists
    list_relevant : list of relevant-ID sets/lists
    k : int
        Cut-off rank.

    Returns
    -------
    float
        Mean Precision@K in [0.0, 1.0].
    """
    if len(list_retrieved) != len(list_relevant):
        raise ValueError(
            "list_retrieved and list_relevant must have the same length."
        )
    scores = [
        precision_at_k(ret, rel, k)
        for ret, rel in zip(list_retrieved, list_relevant)
    ]
    return _safe_mean(scores)


def batch_mrr(
    list_retrieved: List[RetrievedList],
    list_relevant: List[RelevantSet],
) -> float:
    """
    Compute Mean Reciprocal Rank (MRR) over a collection of queries.

    Parameters
    ----------
    list_retrieved : list of retrieved-ID lists
    list_relevant : list of relevant-ID sets/lists

    Returns
    -------
    float
        Mean Reciprocal Rank in [0.0, 1.0].
    """
    if len(list_retrieved) != len(list_relevant):
        raise ValueError(
            "list_retrieved and list_relevant must have the same length."
        )
    scores = [
        mrr(ret, rel)
        for ret, rel in zip(list_retrieved, list_relevant)
    ]
    return _safe_mean(scores)


def batch_ndcg_at_k(
    list_retrieved: List[RetrievedList],
    list_relevant: List[RelevantSet],
    k: int,
) -> float:
    """
    Compute mean NDCG@K over a collection of queries.

    Parameters
    ----------
    list_retrieved : list of retrieved-ID lists
    list_relevant : list of relevant-ID sets/lists
    k : int
        Cut-off rank.

    Returns
    -------
    float
        Mean NDCG@K in [0.0, 1.0].
    """
    if len(list_retrieved) != len(list_relevant):
        raise ValueError(
            "list_retrieved and list_relevant must have the same length."
        )
    scores = [
        ndcg_at_k(ret, rel, k)
        for ret, rel in zip(list_retrieved, list_relevant)
    ]
    return _safe_mean(scores)


# ---------------------------------------------------------------------------
# Self-test (run with `python retrieval_metrics.py`)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _ret = ["c1", "c2", "c3", "c4", "c5"]
    _rel = {"c1", "c3"}

    print("Single-query tests")
    print(f"  Recall@3:     {recall_at_k(_ret, _rel, 3):.4f}")   # 0.5
    print(f"  Recall@5:     {recall_at_k(_ret, _rel, 5):.4f}")   # 1.0
    print(f"  Precision@3:  {precision_at_k(_ret, _rel, 3):.4f}") # 0.3333
    print(f"  MRR:          {mrr(_ret, _rel):.4f}")               # 1.0
    print(f"  NDCG@5:       {ndcg_at_k(_ret, _rel, 5):.4f}")
    print(f"  AP:           {average_precision(_ret, _rel):.4f}")

    print("\nBatch tests")
    list_ret = [["c1","c2","c3","c4","c5"], ["c2","c5","c1","c4","c3"]]
    list_rel = [["c1","c3"], ["c2","c4"]]
    print(f"  Batch Recall@5:  {batch_recall_at_k(list_ret, list_rel, 5):.4f}")
    print(f"  Batch Prec@3:    {batch_precision_at_k(list_ret, list_rel, 3):.4f}")
    print(f"  Batch MRR:       {batch_mrr(list_ret, list_rel):.4f}")
    print(f"  Batch NDCG@5:    {batch_ndcg_at_k(list_ret, list_rel, 5):.4f}")
