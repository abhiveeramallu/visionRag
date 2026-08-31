"""
evaluation/metrics/answer_metrics.py
======================================
Answer quality metrics for VisionRAG-X.

⚠️  NOT YET VALIDATED — All functions in this module are research
implementations.  None have been validated against a standardised
benchmark or human annotation study.  Use with caution; treat outputs
as indicative, not authoritative.

Implemented metrics
-------------------
- exact_match
- token_f1
- citation_accuracy
- hallucination_rate_heuristic

Usage
-----
    from evaluation.metrics.answer_metrics import token_f1, hallucination_rate_heuristic

    pred = "Merge sort has O(n log n) time complexity."
    gt   = "The time complexity of merge sort is O(n log n)."
    print(token_f1(pred, gt))  # ~0.50 depending on tokenisation
"""

from __future__ import annotations

import re
import string
from collections import Counter
from typing import List, Optional, Sequence


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """
    Normalise a text string for comparison:
    - Lowercase
    - Strip punctuation
    - Collapse whitespace
    """
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenise(text: str) -> List[str]:
    """Split normalised text into tokens."""
    return _normalise(text).split()


def _ngrams(tokens: List[str], n: int) -> Counter:
    """Return a Counter of n-grams from a token list."""
    return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


# ---------------------------------------------------------------------------
# Exact Match
# ---------------------------------------------------------------------------

def exact_match(prediction: str, ground_truth: str) -> float:
    """
    Compute the Exact Match score between a predicted answer and
    a ground-truth answer.

    .. warning::
        NOT YET VALIDATED — This metric has not been evaluated
        against human annotations or a standardised benchmark.

    Both strings are normalised (lowercased, punctuation removed,
    whitespace collapsed) before comparison.

    Parameters
    ----------
    prediction : str
        The model-generated answer.
    ground_truth : str
        The reference (gold) answer.

    Returns
    -------
    float
        1.0 if the normalised strings match exactly, 0.0 otherwise.

    Examples
    --------
    >>> exact_match("O(n log n)", "O(n log n)")
    1.0
    >>> exact_match("O(n log n)", "O(n²)")
    0.0
    >>> exact_match("The answer is 42.", "the answer is 42")
    1.0
    """
    return 1.0 if _normalise(prediction) == _normalise(ground_truth) else 0.0


# ---------------------------------------------------------------------------
# Token F1
# ---------------------------------------------------------------------------

def token_f1(prediction: str, ground_truth: str) -> float:
    """
    Compute the token-overlap F1 score between a predicted answer and
    a ground-truth answer.

    This is the standard SQuAD-style token F1:

        precision = |pred_tokens ∩ gt_tokens| / |pred_tokens|
        recall    = |pred_tokens ∩ gt_tokens| / |gt_tokens|
        F1        = 2 * precision * recall / (precision + recall)

    Token intersection accounts for token frequency (uses Counter).

    .. warning::
        NOT YET VALIDATED — This metric has not been evaluated
        against human annotations or a standardised benchmark.

    Parameters
    ----------
    prediction : str
        The model-generated answer.
    ground_truth : str
        The reference (gold) answer.

    Returns
    -------
    float
        Token F1 in [0.0, 1.0].  Returns 0.0 if either string is empty
        after normalisation.

    Examples
    --------
    >>> token_f1("merge sort is O n log n", "the time complexity of merge sort is O n log n")
    0.7272727272727272
    """
    pred_tokens = _tokenise(prediction)
    gt_tokens   = _tokenise(ground_truth)

    if not pred_tokens or not gt_tokens:
        return 0.0

    pred_counter = Counter(pred_tokens)
    gt_counter   = Counter(gt_tokens)

    # Element-wise minimum (intersection)
    common = sum((pred_counter & gt_counter).values())

    if common == 0:
        return 0.0

    precision = common / len(pred_tokens)
    recall    = common / len(gt_tokens)
    f1 = 2 * precision * recall / (precision + recall)
    return f1


# ---------------------------------------------------------------------------
# Citation Accuracy
# ---------------------------------------------------------------------------

def citation_accuracy(
    answer_citations: Sequence[str],
    retrieved_evidence: Sequence[str],
) -> float:
    """
    Compute citation accuracy: the fraction of citations in the answer
    that appear in the set of retrieved evidence IDs.

    A "citation" here is a document/chunk/frame ID string that the model
    included in its answer.  A citation is considered accurate if it
    matches an ID in the retrieved evidence pool.

    .. warning::
        NOT YET VALIDATED — This metric has not been evaluated
        against human annotations or a standardised benchmark.
        It only checks ID membership, not semantic correctness.

    Parameters
    ----------
    answer_citations : sequence of str
        IDs cited in the model's answer.
    retrieved_evidence : sequence of str
        IDs of evidence chunks that were retrieved and passed to the model.

    Returns
    -------
    float
        Fraction of cited IDs that are in the retrieved evidence set.
        Returns 1.0 if ``answer_citations`` is empty (vacuously accurate).

    Examples
    --------
    >>> citation_accuracy(["c1", "c3", "c99"], ["c1", "c2", "c3", "c4"])
    0.6666666666666666
    """
    if not answer_citations:
        return 1.0  # No citations → vacuously accurate

    evidence_set = set(retrieved_evidence)
    hits = sum(1 for cit in answer_citations if cit in evidence_set)
    return hits / len(answer_citations)


# ---------------------------------------------------------------------------
# Hallucination Rate (heuristic)
# ---------------------------------------------------------------------------

def hallucination_rate_heuristic(
    answer: str,
    retrieved_context: str,
    ngram_size: int = 4,
    coverage_threshold: float = 0.5,
) -> float:
    """
    Estimate a hallucination rate for a generated answer using n-gram
    coverage against the retrieved context.

    **Heuristic reasoning**: If a large proportion of the answer's n-grams
    are not found in the retrieved context, the model is likely generating
    content beyond what it was grounded on — a hallucination signal.

    ``hallucination_rate = 1.0 - ngram_coverage``

    where:

    ``ngram_coverage = |answer_ngrams ∩ context_ngrams| / |answer_ngrams|``

    .. warning::
        NOT YET VALIDATED — This is a crude lexical heuristic.
        It will over-penalise paraphrased-but-correct answers and
        under-penalise answers that copy irrelevant passages verbatim.
        Do not use this as the sole measure of faithfulness.

    Parameters
    ----------
    answer : str
        The model-generated answer to evaluate.
    retrieved_context : str
        Concatenated text of all retrieved evidence chunks.
    ngram_size : int, optional
        Size of n-grams to use for overlap (default: 4).
    coverage_threshold : float, optional
        Unused in the current implementation; reserved for future
        thresholding behaviour.

    Returns
    -------
    float
        Estimated hallucination rate in [0.0, 1.0].
        0.0 → fully grounded; 1.0 → no overlap with context.

    Examples
    --------
    >>> ctx = "merge sort divides the array recursively and merges sorted halves"
    >>> ans = "merge sort divides the array recursively and merges sorted halves"
    >>> hallucination_rate_heuristic(ans, ctx)
    0.0
    >>> hallucination_rate_heuristic("dragons invented sorting algorithms", ctx)
    1.0
    """
    answer_tokens  = _tokenise(answer)
    context_tokens = _tokenise(retrieved_context)

    if not answer_tokens:
        return 0.0  # Empty answer — nothing to hallucinate

    if not context_tokens:
        # No context retrieved — assume maximum hallucination
        return 1.0

    answer_ngrams  = _ngrams(answer_tokens, ngram_size)
    context_ngrams = _ngrams(context_tokens, ngram_size)

    if not answer_ngrams:
        # Answer shorter than n — fall back to unigram coverage
        answer_ngrams  = Counter(answer_tokens)
        context_ngrams = Counter(context_tokens)

    total_answer_ngrams = sum(answer_ngrams.values())
    if total_answer_ngrams == 0:
        return 0.0

    overlap = sum((answer_ngrams & context_ngrams).values())
    coverage = overlap / total_answer_ngrams
    return 1.0 - coverage


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def batch_exact_match(
    predictions: Sequence[str],
    ground_truths: Sequence[str],
) -> float:
    """
    Compute mean Exact Match over a list of (prediction, ground_truth) pairs.

    .. warning::
        NOT YET VALIDATED.

    Parameters
    ----------
    predictions : sequence of str
    ground_truths : sequence of str

    Returns
    -------
    float
        Mean Exact Match in [0.0, 1.0].
    """
    if len(predictions) != len(ground_truths):
        raise ValueError("predictions and ground_truths must have the same length.")
    if not predictions:
        return 0.0
    scores = [exact_match(p, g) for p, g in zip(predictions, ground_truths)]
    return sum(scores) / len(scores)


def batch_token_f1(
    predictions: Sequence[str],
    ground_truths: Sequence[str],
) -> float:
    """
    Compute mean Token F1 over a list of (prediction, ground_truth) pairs.

    .. warning::
        NOT YET VALIDATED.

    Parameters
    ----------
    predictions : sequence of str
    ground_truths : sequence of str

    Returns
    -------
    float
        Mean Token F1 in [0.0, 1.0].
    """
    if len(predictions) != len(ground_truths):
        raise ValueError("predictions and ground_truths must have the same length.")
    if not predictions:
        return 0.0
    scores = [token_f1(p, g) for p, g in zip(predictions, ground_truths)]
    return sum(scores) / len(scores)


# ---------------------------------------------------------------------------
# Self-test (run with `python answer_metrics.py`)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Exact Match ===")
    print(exact_match("O(n log n)", "O(n log n)"))         # 1.0
    print(exact_match("O(n log n)", "o(n log n)"))         # 1.0 (case-insensitive)
    print(exact_match("O(n log n)", "O(n squared)"))       # 0.0

    print("\n=== Token F1 ===")
    pred = "merge sort runs in O n log n time"
    gt   = "the time complexity of merge sort is O n log n"
    print(f"Token F1: {token_f1(pred, gt):.4f}")

    print("\n=== Citation Accuracy ===")
    cites    = ["c1", "c3", "c99"]
    evidence = ["c1", "c2", "c3", "c4"]
    print(f"Citation Accuracy: {citation_accuracy(cites, evidence):.4f}")  # 0.6667

    print("\n=== Hallucination Rate (heuristic) ===")
    context = (
        "merge sort divides the array recursively into halves "
        "and then merges the sorted halves back together giving "
        "an O n log n time complexity in all cases"
    )
    faithful_answer = (
        "merge sort divides the array recursively into halves "
        "and merges them"
    )
    hallucinated_answer = "dragons invented sorting algorithms in medieval times"

    print(f"Faithful answer HR:    {hallucination_rate_heuristic(faithful_answer, context):.4f}")
    print(f"Hallucinated answer HR:{hallucination_rate_heuristic(hallucinated_answer, context):.4f}")
