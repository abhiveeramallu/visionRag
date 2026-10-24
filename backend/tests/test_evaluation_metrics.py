"""
Unit tests for evaluation metrics (retrieval and answer metrics).
"""
import sys
from pathlib import Path

# Add project root to path so 'evaluation' module is found
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from evaluation.metrics.retrieval_metrics import (
    recall_at_k,
    precision_at_k,
    mrr,
    ndcg_at_k,
    average_precision,
    batch_recall_at_k,
    batch_precision_at_k,
    batch_mrr,
    batch_ndcg_at_k,
)
from evaluation.metrics.answer_metrics import (
    exact_match,
    token_f1,
    citation_grounding,
    citation_accuracy,
    citation_precision_gold,
    citation_recall_gold,
    citation_f1_gold,
    citation_support_rate,
    is_abstention_response,
    hallucination_rate_heuristic,
    batch_exact_match,
    batch_token_f1,
)


def test_retrieval_recall_and_precision():
    retrieved = ["a", "b", "c", "d"]
    relevant = {"a", "c", "e"}
    assert recall_at_k(retrieved, relevant, k=3) == pytest.approx(2 / 3)
    assert precision_at_k(retrieved, relevant, k=3) == pytest.approx(2 / 3)
    assert recall_at_k(retrieved, set(), k=3) == 0.0


def test_mrr_metric():
    assert mrr(["x", "a", "b"], {"a", "c"}) == 0.5
    assert mrr(["x", "y", "z"], {"a"}) == 0.0
    assert mrr(["a", "b"], {"a"}) == 1.0


def test_ndcg_at_k():
    assert ndcg_at_k(["a", "b", "c"], {"a"}, k=3) == 1.0
    assert ndcg_at_k(["x", "a", "c"], {"a"}, k=3) < 1.0
    assert ndcg_at_k(["x", "y"], {"a"}, k=3) == 0.0


def test_ndcg_at_k_duplicate_regression():
    # Regression test: duplicate retrieved items must NOT push NDCG > 1.0
    retrieved_with_dupes = ["a", "a", "a", "b"]
    score = ndcg_at_k(retrieved_with_dupes, {"a"}, k=4)
    assert score <= 1.0
    assert score == pytest.approx(1.0)

    # Duplicates of non-first item
    retrieved_with_dupes_2 = ["x", "a", "a", "b"]
    score_2 = ndcg_at_k(retrieved_with_dupes_2, {"a"}, k=4)
    assert score_2 <= 1.0


def test_batch_retrieval_metrics():
    ret_list = [["a", "b"], ["x", "y"]]
    rel_list = [["a"], ["y"]]
    assert batch_recall_at_k(ret_list, rel_list, k=2) == 1.0
    assert batch_precision_at_k(ret_list, rel_list, k=2) == 0.5
    assert batch_mrr(ret_list, rel_list) == pytest.approx((1.0 + 0.5) / 2)


def test_exact_match():
    assert exact_match("O(n log n)", "o(n log n)") == 1.0
    assert exact_match("O(n log n)", "O(n^2)") == 0.0


def test_token_f1():
    pred = "merge sort runs in O(n log n) time"
    gt = "merge sort time complexity is O(n log n)"
    score = token_f1(pred, gt)
    assert 0.5 < score < 1.0
    assert token_f1("identical string", "identical string") == 1.0
    assert token_f1("apples", "oranges") == 0.0


def test_citation_accuracy():
    cites = ["c1", "c3", "c99"]
    evidence = ["c1", "c2", "c3", "c4"]
    assert citation_accuracy(cites, evidence) == pytest.approx(2 / 3)
    assert citation_accuracy([], evidence) == 1.0


def test_hallucination_rate_heuristic():
    context = "merge sort divides array recursively and merges sorted halves"
    faithful = "merge sort divides array recursively"
    hallucinated = "aliens built the pyramids in ancient egypt"
    assert hallucination_rate_heuristic(faithful, context) == 0.0
    assert hallucination_rate_heuristic(hallucinated, context) == 1.0


def test_empty_results_retrieval_metrics():
    """Empty retrieved list and empty relevant set evaluate cleanly to 0.0."""
    assert recall_at_k([], {"a"}, k=5) == 0.0
    assert precision_at_k([], {"a"}, k=5) == 0.0
    assert mrr([], {"a"}) == 0.0
    assert ndcg_at_k([], {"a"}, k=5) == 0.0
    assert recall_at_k(["a", "b"], set(), k=5) == 0.0
    assert ndcg_at_k(["a", "b"], set(), k=5) == 0.0


def test_duplicate_retrieved_ids_precision_bounded():
    """Duplicate retrieved document IDs must not inflate Precision@K."""
    retrieved = ["a", "a", "b"]
    assert precision_at_k(retrieved, {"a"}, k=3) == pytest.approx(1 / 3)


def test_perfect_ranking_retrieval_metrics():
    """Top-K matching relevant set perfectly scores 1.0 across all retrieval metrics."""
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    assert recall_at_k(retrieved, relevant, k=3) == 1.0
    assert precision_at_k(retrieved, relevant, k=3) == 1.0
    assert mrr(retrieved, relevant) == 1.0
    assert ndcg_at_k(retrieved, relevant, k=3) == 1.0


def test_citation_gold_precision_and_recall():
    """Gold-standard citation precision, recall, and F1."""
    emitted = ["c1", "c2"]
    gold = ["c1", "c3"]
    assert citation_precision_gold(emitted, gold) == 0.5
    assert citation_recall_gold(emitted, gold) == 0.5
    assert citation_f1_gold(emitted, gold) == 0.5

    # Incorrect citation
    assert citation_precision_gold(["c_wrong"], gold) == 0.0
    assert citation_recall_gold([], gold) == 0.0

    # Vacuous / correct empty citation on unanswerable query
    assert citation_precision_gold([], []) == 1.0
    assert citation_recall_gold([], []) == 1.0

    # Erroneous phantom citation on unanswerable query
    assert citation_precision_gold(["phantom"], []) == 0.0
    assert citation_recall_gold(["phantom"], []) == 0.0


def test_citation_support_rate():
    """Verifies whether cited chunks contain supporting concepts for the answer."""
    corpus = {
        "ku_01": {
            "concept": "Merge Sort Complexity",
            "content": "Merge sort divides array recursively and runs in O(n log n) time.",
        }
    }
    supported_ans = "Merge sort divides array recursively in O(n log n) time."
    unsupported_ans = "Ancient pyramids were constructed with sandstone monoliths."

    assert citation_support_rate(["ku_01"], corpus, supported_ans) == 1.0
    assert citation_support_rate(["ku_01"], corpus, unsupported_ans) == 0.0
    # Abstention response with no citations is validly supported
    assert citation_support_rate([], corpus, "The sources provide insufficient evidence.") == 1.0


def test_abstention_decision_answerable_and_unanswerable():
    """Evaluates refusal response detection on unanswerable vs answerable queries."""
    refusal = "The provided educational sources do not establish this answer; insufficient evidence."
    informative = "Newton's second law is F = m * a."

    assert is_abstention_response(refusal) is True
    assert is_abstention_response(informative) is False


def test_abstention_out_of_domain_with_generic_overlap():
    """
    Out-of-domain query sharing generic terms ('time', 'complexity') with an in-domain unit
    must still trigger abstention when none of its distinctive subject terms match.
    """
    import re
    query = "What is the time complexity of quantum Fourier transform in Shor's algorithm?"
    top_chunk_words = {"merge", "sort", "divides", "recursively", "time", "complexity", "worst"}

    STOPWORDS = {
        'a', 'an', 'the', 'in', 'on', 'at', 'of', 'to', 'for', 'with', 'by', 'as',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'do', 'does', 'did', 'from', 'this', 'that', 'these', 'those', 'it', 'its',
        'they', 'them', 'their', 'we', 'us', 'our', 'you', 'your', 'and', 'or', 'not',
        'but', 'if', 'then', 'else', 'me', 'my'
    }
    GENERIC_QUERY_TERMS = {
        'what', 'which', 'where', 'when', 'show', 'explain', 'tell', 'how',
        'time', 'complexity', 'algorithm', 'formula', 'data', 'structure', 'state',
        'value', 'used', 'using', 'calculate', 'function', 'case', 'equation', 'rule'
    }
    q_tokens = re.findall(r'\b[a-zA-Z0-9_\^²³]{2,}\b', query.lower())
    content_tokens = [t for t in q_tokens if t not in STOPWORDS]
    subject_tokens = [t for t in content_tokens if t not in GENERIC_QUERY_TERMS]
    overlap_subj = [t for t in subject_tokens if t in top_chunk_words]

    max_score = 0.58  # High score due to generic word overlap
    should_abstain = (max_score < 0.20) or (len(subject_tokens) > 0 and len(overlap_subj) == 0)

    assert set(subject_tokens) == {"quantum", "fourier", "transform", "shor"}
    assert len(overlap_subj) == 0
    assert should_abstain is True


def test_abstention_in_domain_paraphrase_preserves_recall():
    """
    Paraphrased in-domain query about merge sort must NOT trigger abstention.
    """
    import re
    query = "How quickly does merge sort finish running on an array?"
    top_chunk_words = {"merge", "sort", "divides", "recursively", "time", "complexity", "log"}

    STOPWORDS = {
        'a', 'an', 'the', 'in', 'on', 'at', 'of', 'to', 'for', 'with', 'by', 'as',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'do', 'does', 'did', 'from', 'this', 'that', 'these', 'those', 'it', 'its',
        'they', 'them', 'their', 'we', 'us', 'our', 'you', 'your', 'and', 'or', 'not',
        'but', 'if', 'then', 'else', 'me', 'my'
    }
    GENERIC_QUERY_TERMS = {
        'what', 'which', 'where', 'when', 'show', 'explain', 'tell', 'how',
        'time', 'complexity', 'algorithm', 'formula', 'data', 'structure', 'state',
        'value', 'used', 'using', 'calculate', 'function', 'case', 'equation', 'rule'
    }
    q_tokens = re.findall(r'\b[a-zA-Z0-9_\^²³]{2,}\b', query.lower())
    content_tokens = [t for t in q_tokens if t not in STOPWORDS]
    subject_tokens = [t for t in content_tokens if t not in GENERIC_QUERY_TERMS]
    overlap_subj = [t for t in subject_tokens if t in top_chunk_words]

    max_score = 0.65
    should_abstain = (max_score < 0.20) or (len(subject_tokens) > 0 and len(overlap_subj) == 0)

    assert "merge" in overlap_subj
    assert "sort" in overlap_subj
    assert should_abstain is False


