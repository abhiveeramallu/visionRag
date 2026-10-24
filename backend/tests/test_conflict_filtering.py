"""
Unit tests for conflict filtering in RetrievalPipeline.
Tests evidence-aware conflict preservation, distant corrections, short symbols,
and bounded output.
"""
import pytest
from app.retrieval.retrieval_pipeline import RetrievalPipeline


class DummyPipeline:
    filter_relevant_conflicts = RetrievalPipeline.filter_relevant_conflicts


@pytest.fixture
def pipeline():
    return DummyPipeline()


def test_distant_correction_retrieved(pipeline):
    """
    Distant correction: evidence at t=2400s (Slide 25), conflict at t=60s (Slide 2).
    Time delta is 2340s and slides differ, but topic/claim relates to merge sort.
    Must be preserved, not dropped by a 30s cutoff.
    """
    conflicts = [
        {
            "id": "c_merge_sort",
            "type": "complexity_disagreement",
            "concept": "Merge Sort Complexity",
            "claims": ["O(n^2) [asr]", "O(n log n) [ocr]"],
            "timestamp": 60.0,
            "page": 2,
            "resolution": "Instructor corrected slip at 2400s confirming O(n log n).",
        }
    ]
    evidence = [
        {
            "id": "ev_corr",
            "concept": "Merge Sort Correction",
            "content": "Earlier I misspoke when I said O(n^2). Merge sort recurrence solves to O(n log n).",
            "timestamp_start": 2400.0,
            "page": 25,
        }
    ]
    query = "What is the worst case time complexity of merge sort?"
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 1
    assert relevant[0]["id"] == "c_merge_sort"


def test_short_complexity_symbols_preserved(pipeline):
    """
    Short mathematical symbols like O(n) and O(n^2) must not be filtered out
    by string length cutoffs.
    """
    conflicts = [
        {
            "id": "c_linear_vs_quad",
            "type": "complexity_disagreement",
            "claims": ["O(n)", "O(n^2)"],
            "timestamp": 100.0,
        }
    ]
    evidence = [
        {
            "content": "Algorithm complexity is O(n^2) quadratic time.",
            "timestamp_start": 500.0,
        }
    ]
    query = "Is the algorithm O(n) or O(n^2)?"
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 1
    assert relevant[0]["id"] == "c_linear_vs_quad"


def test_short_formula_variables_preserved(pipeline):
    """
    Single-letter variable symbols (m, v, a, f) and exponents (v^2, v²)
    must match correctly.
    """
    conflicts = [
        {
            "id": "c_ke",
            "type": "formula_contradiction",
            "claims": ["KE = 0.5 * m * v^2", "KE = m * v^2"],
            "timestamp": 150.0,
        }
    ]
    evidence = [
        {
            "content": "The kinetic energy equation is KE = 0.5 * m * v².",
            "timestamp_start": 800.0,
        }
    ]
    query = "What is the formula for kinetic energy KE?"
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 1
    assert relevant[0]["id"] == "c_ke"


def test_irrelevant_conflict_excluded(pipeline):
    """
    An unrelated conflict about Dijkstra negative weights must NOT match a Binary Search query.
    """
    conflicts = [
        {
            "id": "c_dijkstra",
            "concept": "Dijkstra Negative Edges",
            "claims": ["Dijkstra handles negative weights", "Dijkstra fails on negative cycles"],
            "timestamp": 500.0,
            "page": 10,
        }
    ]
    evidence = [
        {
            "concept": "Binary Search",
            "content": "Binary search divides the sorted array in halves with O(log n) time.",
            "timestamp_start": 120.0,
            "page": 3,
        }
    ]
    query = "What is the time complexity of binary search?"
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 0


def test_conflict_missing_metadata_handled_safely(pipeline):
    """
    Conflicts with None timestamps, pages, or empty claims do not crash the filter.
    """
    conflicts = [
        {
            "id": "c_empty",
            "claims": [],
            "timestamp": None,
            "page": None,
        }
    ]
    evidence = [
        {
            "content": "Some normal evidence text.",
            "timestamp_start": 10.0,
            "page": 1,
        }
    ]
    query = "Explain the topic."
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 0


def test_conflict_lineage_id_matching(pipeline):
    """
    Conflicts linked by unit_ids to retrieved evidence units are matched across different times.
    """
    conflicts = [
        {
            "id": "c_unit_link",
            "unit_ids": ["ku_01", "ku_02"],
            "claims": ["disagreement"],
            "timestamp": 10.0,
        }
    ]
    evidence = [
        {
            "knowledge_unit_id": "ku_02",
            "content": "Some text",
            "timestamp_start": 900.0,
        }
    ]
    query = "General query"
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 1
    assert relevant[0]["id"] == "c_unit_link"


def test_unrelated_query_with_background_conflict_chunk_excluded(pipeline):
    """
    A binary search query with a background merge-sort unit in the candidate pool
    must NOT receive a merge-sort conflict alert.
    """
    conflicts = [
        {
            "id": "c_merge_sort",
            "concept": "Merge Sort Time Complexity",
            "unit_ids": ["ku_01", "ku_02", "ku_03"],
            "claims": ["O(n^2) [asr]", "O(n log n) [ocr]"],
            "timestamp": 12.0,
        }
    ]
    evidence = [
        {
            "id": "ku_05",
            "concept": "Binary Search Complexity",
            "content": "Binary search runs in O(log n) time complexity.",
            "timestamp_start": 62.0,
        },
        {
            "id": "ku_01",
            "concept": "Merge Sort Time Complexity",
            "content": "Merge sort divides the array recursively and merges sorted halves.",
            "timestamp_start": 12.0,
        }
    ]
    query = "What is the time complexity and auxiliary space of binary search?"
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 0


def test_verified_contradiction_on_topic_included(pipeline):
    """
    When the query is topical (kinetic energy) and evidence units match,
    the verified formula contradiction is retained.
    """
    conflicts = [
        {
            "id": "c_ke",
            "concept": "Kinetic Energy Formula",
            "unit_ids": ["ku_08", "ku_09"],
            "claims": ["KE = 0.5 * m * v^2 [formula]", "KE = m * v^2 [asr]"],
            "timestamp": 142.0,
        }
    ]
    evidence = [
        {
            "id": "ku_08",
            "concept": "Kinetic Energy Slide Equation",
            "content": "Kinetic Energy is KE = 0.5 * m * v^2.",
            "timestamp_start": 140.0,
        }
    ]
    query = "What is the formula for kinetic energy of a moving object?"
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 1
    assert relevant[0]["id"] == "c_ke"


def test_broad_topic_mention_without_disputed_claim_excluded(pipeline):
    """
    A question asking about Depth First Search stack data structure
    must not trigger an algorithm complexity conflict.
    """
    conflicts = [
        {
            "id": "c_merge_sort",
            "concept": "Merge Sort Time Complexity",
            "unit_ids": ["ku_01", "ku_02", "ku_03"],
            "claims": ["O(n^2)", "O(n log n)"],
            "timestamp": 12.0,
        }
    ]
    evidence = [
        {
            "id": "ku_13",
            "concept": "Depth First Search Stack",
            "content": "DFS explores deeply using recursion or a LIFO Stack.",
            "timestamp_start": 230.0,
        }
    ]
    query = "What data structure does Depth First Search utilize?"
    relevant = pipeline.filter_relevant_conflicts(conflicts, evidence, query)
    assert len(relevant) == 0

