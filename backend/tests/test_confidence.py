"""
Unit tests for the ConfidenceScorer module.
"""
import pytest
from app.verification.confidence import ConfidenceScorer


@pytest.fixture
def scorer():
    return ConfidenceScorer()


def test_extraction_score_bounds(scorer):
    assert scorer._extraction_score({'confidence': 0.95}) == 0.95
    assert scorer._extraction_score({'confidence': 1.5}) == 1.0
    assert scorer._extraction_score({'confidence': -0.2}) == 0.0


def test_cross_modal_agreement_high(scorer):
    window = {
        'ocr_segments': [{'text': 'Merge sort runs in O(n log n) time'}],
    }
    seg = {'text': 'Merge sort runs in O(n log n) time', 'modality': 'asr'}
    f1 = scorer._cross_modal_agreement(seg, window)
    assert f1 > 0.8


def test_cross_modal_agreement_low(scorer):
    window = {
        'ocr_segments': [{'text': 'QuickSort average runtime'}],
    }
    seg = {'text': 'Binary trees and AVL rotations', 'modality': 'asr'}
    f1 = scorer._cross_modal_agreement(seg, window)
    assert f1 < 0.2


def test_temporal_consistency_recurrence(scorer):
    windows = [
        {'asr_segments': [{'text': 'The master theorem provides a cookbook method'}]},
        {'asr_segments': [{'text': 'Applying the master theorem to divide and conquer recurrences'}]},
        {'asr_segments': [{'text': 'Here master theorem condition 1 applies'}]},
        {'asr_segments': [{'text': 'Unrelated conclusion section'}]},
    ]
    scorer.build_recurrence_index(windows)

    recurring_seg = {'text': 'master theorem method'}
    isolated_seg = {'text': 'completely novel isolated topic'}

    rec_score = scorer._temporal_consistency(recurring_seg, {})
    iso_score = scorer._temporal_consistency(isolated_seg, {})

    assert rec_score > iso_score
    assert rec_score > 0.6


def test_verification_score_with_and_without_conflict(scorer):
    seg = {'text': 'O(n^2)', 'modality': 'asr', 'timestamp_start': 15.0}

    # No conflicts
    assert scorer._verification_score(seg, []) == 1.0

    # Distant conflict (different timestamp)
    distant_conflict = {
        'sources': ['asr', 'ocr'],
        'timestamp': 100.0,
        'severity': 'high',
    }
    assert scorer._verification_score(seg, [distant_conflict]) == 1.0

    # Nearby high severity conflict
    nearby_conflict = {
        'sources': ['asr', 'ocr'],
        'timestamp': 18.0,
        'severity': 'high',
    }
    assert scorer._verification_score(seg, [nearby_conflict]) < 1.0


def test_score_segment_composite(scorer):
    window = {
        'asr_segments': [{'text': 'Recursion tree method', 'modality': 'asr'}],
        'ocr_segments': [{'text': 'Recursion tree analysis', 'modality': 'ocr'}],
    }
    seg = {'text': 'Recursion tree method', 'modality': 'asr', 'confidence': 0.9, 'timestamp_start': 10.0}
    score = scorer.score_segment(seg, window, [])
    assert 0.0 <= score <= 1.0
    assert score > 0.6


def test_repeated_incorrect_claim_does_not_outrank_correction(scorer):
    """
    A repeated incorrect statement (e.g. O(n^2) slip repeated 4 times)
    must NOT outrank a single, explicit correction (O(n log n) stated once).
    """
    windows = [
        {'asr_segments': [{'text': 'Initial analysis: merge sort has worst case O(n^2) quadratic runtime'}]},
        {'asr_segments': [{'text': 'Remember merge sort quadratic O(n^2)'}]},
        {'asr_segments': [{'text': 'As discussed earlier with merge sort O(n^2)'}]},
        {'asr_segments': [{'text': 'Correction: I misspoke earlier. Merge sort is actually O(n log n).'}]},
    ]
    scorer.build_recurrence_index(windows)

    # Repeated superseded error
    superseded_seg = {
        'text': 'merge sort quadratic runtime O(n^2)',
        'confidence': 0.9,
        'status': 'superseded',
        'modality': 'asr',
    }
    superseded_window = {
        'asr_segments': [{'text': 'merge sort quadratic runtime O(n^2)'}],
        'ocr_segments': [{'text': 'merge sort runtime O(n^2)'}],
    }

    # Single explicit correction
    correction_seg = {
        'text': 'Correction: merge sort recurrence relation solves to O(n log n)',
        'confidence': 0.92,
        'status': 'verified',
        'correction_reason': 'Instructor corrected speech slip',
        'modality': 'asr',
    }
    correction_window = {
        'asr_segments': [{'text': 'Correction: merge sort recurrence relation solves to O(n log n)'}],
        'ocr_segments': [],
    }

    score_error = scorer.score_segment(superseded_seg, superseded_window, [])
    score_correction = scorer.score_segment(correction_seg, correction_window, [])

    # The single explicit correction must decisively outrank the repeated error
    assert score_correction > score_error
    assert score_error <= 0.35
    assert score_correction >= 0.70


def test_low_quality_ocr_penalized(scorer):
    """
    Garbled OCR with high non-alphanumeric noise is penalized in extraction quality.
    """
    clean_ocr = {'text': 'Theorem 1: Convergence of gradient descent', 'confidence': 0.9, 'modality': 'ocr'}
    noisy_ocr = {'text': 'Thm#1: ~~~||||| Conv@@@g descent %%^&&**', 'confidence': 0.9, 'modality': 'ocr'}

    clean_score = scorer._extraction_score(clean_ocr)
    noisy_score = scorer._extraction_score(noisy_ocr)

    assert clean_score == 0.9
    assert noisy_score < clean_score
    assert noisy_score <= 0.6


def test_score_breakdown_explicit_components(scorer):
    """
    score_breakdown must make components explicit and disclaim calibrated probability.
    """
    seg = {'text': 'Binary search runs in logarithmic time O(log n)', 'confidence': 0.95, 'modality': 'asr'}
    window = {'ocr_segments': [{'text': 'Binary search O(log n)'}]}
    breakdown = scorer.score_breakdown(seg, window, [])

    assert 'heuristic_score' in breakdown
    assert 'extraction_quality' in breakdown
    assert 'cross_modal_agreement' in breakdown
    assert 'lexical_recurrence' in breakdown
    assert 'verification_status_score' in breakdown
    assert breakdown['is_calibrated_probability'] is False
    assert 'Heuristic ranking score' in breakdown['note']


def test_isolated_valid_claim_scores_moderately(scorer):
    """
    An isolated valid claim (appearing in 1 window) is not discarded; scores moderately.
    """
    windows = [
        {'asr_segments': [{'text': 'Common sorting algorithms review'}]},
        {'asr_segments': [{'text': 'Graph search breadth first search'}]},
        {'asr_segments': [{'text': 'Unique theorem: Master theorem case 3 condition'}]},
    ]
    scorer.build_recurrence_index(windows)

    isolated_claim = {
        'text': 'Master theorem case 3 condition',
        'confidence': 0.88,
        'modality': 'asr',
    }
    score = scorer.score_segment(isolated_claim, {}, [])
    assert 0.45 <= score <= 0.75
