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
    assert len(conflicts) == 1
    assert conflicts[0]['type'] == 'numeric_disagreement'


def test_formula_contradiction(detector):
    """Different RHS for the same LHS equation should be flagged as formula contradiction."""
    window = make_window(
        asr_text='The kinetic energy equation is KE = 0.5 * m * v^2',
        ocr_text='Kinetic Energy: KE = m * v^2',
    )
    conflicts = detector.detect_in_window(window)
    assert len(conflicts) == 1
    assert conflicts[0]['type'] == 'formula_contradiction'
    assert conflicts[0]['severity'] == 'high'


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


def test_llm_verify_fallback_when_unconfigured(detector):
    """When LLM is not configured, verify_with_llm returns safe unverified candidate without asserting genuine conflict."""
    import asyncio
    res = asyncio.get_event_loop().run_until_complete(
        detector.verify_with_llm({'claims': ['O(n)', 'O(n^2)']}, 'some context')
    )
    assert res['llm_verified'] is False
    assert res['is_genuine_conflict'] is None
    assert res['verification_status'] == 'unverified'
    assert res['status'] == 'candidate'
    assert res['is_candidate'] is True
    assert res['resolved'] is False


def test_llm_verify_network_error(mock_settings):
    """Network/timeout errors preserve candidate status and mark verification as inconclusive."""
    import asyncio
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = TimeoutError("Connection to LLM provider timed out")
    mock_settings.is_llm_configured.return_value = True

    detector = ConflictDetector(mock_settings, llm_client=mock_llm)
    res = asyncio.get_event_loop().run_until_complete(
        detector.verify_with_llm({'claims': ['v1', 'v2']}, 'context')
    )
    assert res['llm_verified'] is False
    assert res['is_genuine_conflict'] is None
    assert res['verification_status'] == 'inconclusive'
    assert res['status'] == 'inconclusive'
    assert 'verification error' in res['resolution']


def test_llm_verify_malformed_json(mock_settings):
    """Malformed non-JSON responses from LLM are handled safely as inconclusive candidates."""
    import asyncio
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Sorry, as an AI language model I cannot answer in JSON."
    mock_settings.is_llm_configured.return_value = True

    detector = ConflictDetector(mock_settings, llm_client=mock_llm)
    res = asyncio.get_event_loop().run_until_complete(
        detector.verify_with_llm({'claims': ['v1', 'v2']}, 'context')
    )
    assert res['llm_verified'] is False
    assert res['is_genuine_conflict'] is None
    assert res['verification_status'] == 'inconclusive'


def test_llm_verify_false_positive_candidate(mock_settings):
    """LLM detecting false-positive marks is_genuine_conflict=False and verification_status='false_positive'."""
    import asyncio
    import json
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = json.dumps({
        'is_genuine_conflict': False,
        'resolution_status': 'not_a_conflict',
        'resolution_explanation': 'Speaker was presenting best case while slide presented average case.',
        'confidence': 0.90,
    })
    mock_settings.is_llm_configured.return_value = True

    detector = ConflictDetector(mock_settings, llm_client=mock_llm)
    res = asyncio.get_event_loop().run_until_complete(
        detector.verify_with_llm({'claims': ['O(n)', 'O(n^2)']}, 'context')
    )
    assert res['llm_verified'] is True
    assert res['is_genuine_conflict'] is False
    assert res['verification_status'] == 'false_positive'
    assert res['status'] == 'not_a_conflict'


def test_llm_verify_unresolved_genuine_conflict(mock_settings):
    """LLM confirming genuine unresolvable contradiction."""
    import asyncio
    import json
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = json.dumps({
        'is_genuine_conflict': True,
        'resolution_status': 'unresolved',
        'resolution_explanation': 'Direct contradiction between slide formula and spoken definition with no clarification.',
        'confidence': 0.88,
    })
    mock_settings.is_llm_configured.return_value = True

    detector = ConflictDetector(mock_settings, llm_client=mock_llm)
    res = asyncio.get_event_loop().run_until_complete(
        detector.verify_with_llm({'claims': ['a', 'b']}, 'context')
    )
    assert res['llm_verified'] is True
    assert res['is_genuine_conflict'] is True
    assert res['verification_status'] == 'verified_contradiction'
    assert res['status'] == 'unresolved'


def test_formula_symbolic_commutativity(detector):
    """E = m * c^2 and E = c^2 * m must NOT be flagged as contradictory."""
    text_asr = "The energy equation is E = m * c^2 in special relativity."
    text_ocr = "Energy equivalence: E = c^2 * m"
    conflict = detector._detect_formula_contradiction(text_asr, text_ocr, 'asr', 'ocr', {})
    assert conflict is None


def test_formula_algebraic_rearrangement(detector):
    """F = m * a and a = F / m are equivalent rearrangements and must NOT be flagged as contradictory."""
    text_asr = "Newton's second law is F = m * a."
    text_ocr = "Acceleration formula: a = F / m"
    conflict = detector._detect_formula_contradiction(text_asr, text_ocr, 'asr', 'ocr', {})
    assert conflict is None


def test_formula_genuine_contradiction_detected(detector):
    """KE = 0.5 * m * v^2 vs KE = m * v^2 represents a genuine mathematical contradiction."""
    text_slide = "Kinetic energy: KE = 0.5 * m * v^2"
    text_speech = "Remember kinetic energy is KE = m * v^2"
    conflict = detector._detect_formula_contradiction(text_speech, text_slide, 'asr', 'ocr', {})
    assert conflict is not None
    assert conflict['type'] == 'formula_contradiction'


def test_formula_unit_normalization(detector):
    """v = 10 m/s vs v = 36 km/h are equivalent under SI unit conversion."""
    text_asr = "The speed is v = 10 m/s."
    text_ocr = "Speed measurement: v = 36 km/h"
    conflict = detector._detect_formula_contradiction(text_asr, text_ocr, 'asr', 'ocr', {})
    assert conflict is None


def test_formula_different_contextual_assumptions(detector):
    """Relativistic vs classical/non-relativistic equations are not contradictory."""
    text_asr = "In the non-relativistic classical regime, kinetic energy is KE = 0.5 * m * v^2."
    text_ocr = "In the relativistic regime, kinetic energy follows KE = (gamma - 1) * m * c^2."
    conflict = detector._detect_formula_contradiction(text_asr, text_ocr, 'asr', 'ocr', {})
    assert conflict is None


def test_formula_malformed_syntax_handled_safely(detector):
    """Malformed equations do not raise exceptions and return None (uncertain)."""
    text_asr = "x = = + ** 5"
    text_ocr = "x = 42"
    conflict = detector._detect_formula_contradiction(text_asr, text_ocr, 'asr', 'ocr', {})
    assert conflict is None


def test_llm_verify_with_mock_llm(mock_settings):
    """With an active LLM client, verify_with_llm parses structured assessment."""
    import asyncio
    import json
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = json.dumps({
        'is_genuine_conflict': True,
        'resolution_status': 'resolved',
        'resolution_explanation': 'Speaker explicitly corrected the complexity at 0:14',
        'confidence': 0.94,
        'recommended_claim': 'O(n log n)',
    })
    mock_settings.is_llm_configured.return_value = True

    detector = ConflictDetector(mock_settings, llm_client=mock_llm)
    res = asyncio.get_event_loop().run_until_complete(
        detector.verify_with_llm({
            'type': 'complexity_disagreement',
            'claims': ['O(n^2)', 'O(n log n)'],
            'sources': ['asr', 'ocr'],
            'confidence': 0.8,
        }, 'Context text')
    )
    assert res['llm_verified'] is True
    assert res['resolved'] is True
    assert res['status'] == 'resolved'
    assert 'explicitly corrected' in res['resolution']
    assert res['confidence'] == 0.94


def test_verify_all_with_llm_preserves_unresolved_and_filters_false_positives(mock_settings):
    """verify_all_with_llm must filter out confirmed false positives but preserve unresolved candidates."""
    import asyncio
    import json
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    # Return different responses for different calls
    mock_llm.complete.side_effect = [
        # Call 1: False positive
        json.dumps({
            'is_genuine_conflict': False,
            'resolution_status': 'not_a_conflict',
            'resolution_explanation': 'Different contexts',
            'confidence': 0.9,
        }),
        # Call 2: Genuine contradiction
        json.dumps({
            'is_genuine_conflict': True,
            'resolution_status': 'unresolved',
            'resolution_explanation': 'Contradiction on slide',
            'confidence': 0.92,
        }),
        # Call 3: Inconclusive / parse failure fallback
        "Invalid non-json output",
    ]
    mock_settings.is_llm_configured.return_value = True

    detector = ConflictDetector(mock_settings, llm_client=mock_llm)
    conflicts = [
        {'id': 'c1', 'claims': ['claim1a', 'claim1b']},
        {'id': 'c2', 'claims': ['claim2a', 'claim2b']},
        {'id': 'c3', 'claims': ['claim3a', 'claim3b']},
    ]

    verified = asyncio.get_event_loop().run_until_complete(
        detector.verify_all_with_llm(conflicts, {}, filter_false_positives=True)
    )

    # c1 (false positive) must be filtered out
    # c2 (genuine contradiction) must be preserved
    # c3 (inconclusive candidate) must be preserved!
    assert len(verified) == 2
    assert verified[0]['id'] == 'c2'
    assert verified[0]['is_genuine_conflict'] is True
    assert verified[1]['id'] == 'c3'
    assert verified[1]['is_genuine_conflict'] is None
    assert verified[1]['verification_status'] == 'inconclusive'

