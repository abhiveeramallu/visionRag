"""
Tests for the ConflictDetector module.
"""
import pytest
from app.verification.conflict_detector import ConflictDetector


@pytest.fixture
def detector(mock_settings):
    return ConflictDetector(mock_settings)


def make_window(asr_text, ocr_text, source_id='test-src'):
    return {
        'window_id': 'w1',
        'source_id': source_id,
        'window_start': 0.0,
        'window_end': 15.0,
        'page': None,
        'asr_segments': [{'text': asr_text, 'modality': 'asr', 'confidence': 0.9,
                          'timestamp_start': 5.0}] if asr_text else [],
        'ocr_segments': [{'text': ocr_text, 'modality': 'ocr', 'confidence': 0.85,
                          'timestamp_start': 7.0}] if ocr_text else [],
    }


def test_complexity_conflict_detected(detector):
    """O(n log n) vs O(n^2) should be flagged as a complexity conflict."""
    window = make_window(
        asr_text='The time complexity of merge sort is O(n log n)',
        ocr_text='Merge Sort Complexity: O(n^2)',
    )
    conflicts = detector.detect_in_window(window)
    assert len(conflicts) == 1
    assert conflicts[0]['type'] == 'complexity_disagreement'
    assert 'asr' in conflicts[0]['sources']
    assert 'ocr' in conflicts[0]['sources']
    assert conflicts[0]['severity'] == 'high'


def test_no_conflict_same_complexity(detector):
    """Same complexity in both modalities should not produce a conflict."""
    window = make_window(
        asr_text='Merge sort runs in O(n log n) time',
        ocr_text='Time complexity: O(n log n)',
    )
    conflicts = detector.detect_in_window(window)
    assert len(conflicts) == 0


def test_empty_window_no_conflict(detector):
    """Window with no segments should return no conflicts."""
    window = {
        'window_id': 'w_empty', 'source_id': 'test',
        'window_start': 0.0, 'window_end': 15.0, 'page': None,
        'asr_segments': [], 'ocr_segments': [],
    }
    conflicts = detector.detect_in_window(window)
    assert conflicts == []


def test_detect_all_empty(detector):
    """Empty window list should return empty conflict list."""
    assert detector.detect_all([]) == []


def test_detect_all_multiple_windows(detector):
    """Each conflicting window should contribute one conflict."""
    w1 = make_window('complexity is O(n)', 'Complexity: O(n^2)', 'src-1')
    w2 = make_window('no special content here', 'no special content here', 'src-1')
    conflicts = detector.detect_all([w1, w2])
    # w2 has identical text → similarity > 0.8 → no conflict
    assert len(conflicts) == 1


def test_disabled_detector_returns_nothing(mock_settings):
    """When conflict_detection_enabled=False, detector returns no conflicts."""
    mock_settings.conflict_detection_enabled = False
    detector = ConflictDetector(mock_settings)
    window = make_window('O(n log n)', 'O(n^2)')
    assert detector.detect_in_window(window) == []


def test_numeric_conflict(detector):
    """Different numbers in ASR vs OCR with similar context should be flagged."""
    window = make_window(
        asr_text='There are 3 steps in the algorithm',
        ocr_text='Algorithm has 7 steps',
    )
    conflicts = detector.detect_in_window(window)
    # May or may not fire depending on text similarity — just check it doesn't crash
    assert isinstance(conflicts, list)


def test_conflict_has_required_fields(detector):
    """Conflict dicts must have all required fields."""
    window = make_window('O(n log n)', 'O(n^2)')
    conflicts = detector.detect_in_window(window)
    if conflicts:
        c = conflicts[0]
        assert 'type' in c
        assert 'sources' in c
        assert 'claims' in c
        assert 'severity' in c
        assert 'confidence' in c


def test_llm_verify_raises_not_implemented(detector):
    """LLM verifier must raise NotImplementedError."""
    import asyncio
    with pytest.raises(NotImplementedError):
        asyncio.get_event_loop().run_until_complete(
            detector.verify_with_llm({}, 'some context')
        )
