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
# Citation Metrics (Faithfulness & Ground Truth Precision/Recall)
# ---------------------------------------------------------------------------

def citation_grounding(
    answer_citations: Sequence[str],
    retrieved_evidence: Sequence[str],
) -> float:
    """
    Compute citation grounding / faithfulness: the fraction of citations in the
    answer that appear in the set of retrieved evidence IDs passed to the generator.

    Faithfulness = |citations ∩ retrieved_evidence| / |citations|

    Parameters
    ----------
    answer_citations : sequence of str
        IDs cited in the model's answer.
    retrieved_evidence : sequence of str
        IDs of evidence chunks that were retrieved and passed to the model.

    Returns
    -------
    float
        Grounding score in [0.0, 1.0].  Returns 1.0 if ``answer_citations`` is empty
        (i.e., when abstaining or citing nothing ungrounded).
    """
    if not answer_citations:
        return 1.0

    evidence_set = set(retrieved_evidence)
    hits = sum(1 for cit in answer_citations if cit in evidence_set)
    return hits / len(answer_citations)


# Backward-compatible alias for citation_grounding
citation_accuracy = citation_grounding


def citation_precision_gold(
    answer_citations: Sequence[str],
    gold_citations: Sequence[str],
) -> float:
    """
    Compute citation precision against independent gold-standard evidence IDs.

    Precision = |citations ∩ gold_citations| / |citations|

    Returns 1.0 if both citations and gold_citations are empty (e.g. unanswerable query).
    Returns 0.0 if citations were emitted when gold is empty, or if no citations were emitted when gold is non-empty.
    """
    c_set = set(answer_citations)
    g_set = set(gold_citations)

    if not c_set:
        return 1.0 if not g_set else 0.0
    if not g_set:
        return 0.0

    hits = len(c_set & g_set)
    return hits / len(c_set)


def citation_recall_gold(
    answer_citations: Sequence[str],
    gold_citations: Sequence[str],
) -> float:
    """
    Compute citation recall against independent gold-standard evidence IDs.

    Recall = |citations ∩ gold_citations| / |gold_citations|

    Returns 1.0 if both citations and gold_citations are empty.
    Returns 0.0 if gold is non-empty and no citations were emitted.
    """
    c_set = set(answer_citations)
    g_set = set(gold_citations)

    if not g_set:
        return 1.0 if not c_set else 0.0
    if not c_set:
        return 0.0

    hits = len(c_set & g_set)
    return hits / len(g_set)


def citation_f1_gold(
    answer_citations: Sequence[str],
    gold_citations: Sequence[str],
) -> float:
    """
    Compute citation F1 against gold-standard evidence IDs.
    """
    p = citation_precision_gold(answer_citations, gold_citations)
    r = citation_recall_gold(answer_citations, gold_citations)
    if p + r == 0:
        return 0.0
    return 2.0 * p * r / (p + r)


def citation_support_rate(
    answer_citations: Sequence[str],
    corpus_by_id: dict,
    answer_text: str,
) -> float:
    """
    Verify whether each cited source genuinely contains and supports the concepts
    asserted in the model answer.

    For each cited ID:
    - Verifies the chunk exists in corpus.
    - Checks for lexical overlap of substantive words (>= 4 chars) between the chunk content
      and the answer text.
    """
    if not answer_citations:
        # If no citations emitted: considered supported if answer correctly abstained
        if is_abstention_response(answer_text):
            return 1.0
        return 0.0

    answer_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', answer_text.lower()))
    if not answer_words:
        return 1.0

    supported_count = 0
    for cid in answer_citations:
        chunk = corpus_by_id.get(cid)
        if not chunk:
            continue
        chunk_text = (chunk.get("concept", "") + " " + chunk.get("content", "")).lower()
        chunk_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', chunk_text))
        if answer_words & chunk_words:
            supported_count += 1

    return supported_count / len(answer_citations)


ABSTENTION_PHRASES = [
    "insufficient evidence",
    "does not contain",
    "do not establish",
    "cannot be answered",
    "not provided",
    "not mentioned",
    "no information",
    "unable to answer",
]


def is_abstention_response(answer_text: str) -> bool:
    """Check if the answer text expresses abstention / insufficient evidence."""
    if not answer_text or not answer_text.strip():
        return True
    lowered = answer_text.lower()
    return any(phrase in lowered for phrase in ABSTENTION_PHRASES)


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
