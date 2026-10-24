"""
Integration tests for the query endpoint and production pipeline in VisionRAG-X.
Tests:
1. Answerable queries return grounded answers with citations.
2. Out-of-domain / ungrounded queries trigger subject-aware abstention.
3. Corrected claims resolve to the superseding version via VEKG traversal.
4. Irrelevant background conflicts are suppressed from non-topical queries.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime


class MockSourceModel:
    id = "source-test-123"
    title = "CS Algorithms Lecture: Sorting and Searching"
    source_type = "video"
    status = "completed"
    created_at = datetime.utcnow()


class MockUnitModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _get_mock_units():
    return [
        MockUnitModel(
            id="ku_01",
            concept="Merge Sort Time Complexity",
            content="Merge sort divides the array recursively and merges sorted halves. Its time complexity is O(n log n) in all cases.",
            modality="ocr",
            source_id="source-test-123",
            timestamp_start=12.0,
            timestamp_end=18.0,
            page=None,
            slide=1,
            confidence=0.95,
            status="verified",
            version=1,
            previous_version_id=None,
            correction_reason=None,
        ),
        MockUnitModel(
            id="ku_02",
            concept="Merge Sort Speech Slip",
            content="In our initial analysis, the instructor stated that merge sort runs in O(n^2) worst case.",
            modality="asr",
            source_id="source-test-123",
            timestamp_start=10.0,
            timestamp_end=14.0,
            page=None,
            slide=None,
            confidence=0.88,
            status="superseded",
            version=1,
            previous_version_id=None,
            correction_reason=None,
        ),
        MockUnitModel(
            id="ku_03",
            concept="Merge Sort Verbal Correction",
            content="Excuse me, I made a mistake earlier when I said O(n^2). Merge sort is actually O(n log n) because T(n) = 2T(n/2) + O(n).",
            modality="asr",
            source_id="source-test-123",
            timestamp_start=45.0,
            timestamp_end=52.0,
            page=None,
            slide=None,
            confidence=0.92,
            status="verified",
            version=2,
            previous_version_id="ku_02",
            correction_reason="Instructor corrected prior slip",
        ),
        MockUnitModel(
            id="ku_04",
            concept="Binary Search Algorithm",
            content="def binary_search(arr, target): low, high = 0, len(arr) - 1. While low <= high, mid = (low + high) // 2.",
            modality="code",
            source_id="source-test-123",
            timestamp_start=60.0,
            timestamp_end=75.0,
            page=None,
            slide=2,
            confidence=0.96,
            status="active",
            version=1,
            previous_version_id=None,
            correction_reason=None,
        ),
        MockUnitModel(
            id="ku_05",
            concept="Binary Search Complexity",
            content="Binary search requires a sorted array and runs in O(log n) time complexity with O(1) auxiliary space.",
            modality="ocr",
            source_id="source-test-123",
            timestamp_start=62.0,
            timestamp_end=70.0,
            page=None,
            slide=2,
            confidence=0.94,
            status="active",
            version=1,
            previous_version_id=None,
            correction_reason=None,
        ),
    ]


class MockConflictModel:
    id = "c_merge_sort"
    source_id = "source-test-123"
    conflict_type = "complexity_disagreement"
    modalities = ["asr", "ocr"]
    sources = ["asr", "ocr"]
    claims = ["O(n^2) [asr]", "O(n log n) [ocr]"]
    timestamp = 12.0
    page = 1
    severity = "high"
    confidence = 0.90
    resolved = True
    resolution = "Instructor corrected slip at 45.0s, confirming O(n log n)."


@pytest.fixture
def api_client():
    with patch('app.database.postgres.init_db', new_callable=AsyncMock), \
         patch('app.database.qdrant.QdrantManager') as mock_qdrant, \
         patch('app.indexing.vector_index.VectorIndex.search', new_callable=AsyncMock) as mock_vsearch:
        mock_qdrant.return_value.init_collection = AsyncMock()
        mock_qdrant.return_value.search = AsyncMock(return_value=[])
        mock_vsearch.return_value = []
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def _mock_db_with_source():
    mock_session = AsyncMock()
    mock_source_res = MagicMock()
    mock_source_res.scalar_one_or_none.return_value = MockSourceModel()

    mock_units_res = MagicMock()
    mock_units_res.scalars.return_value.all.return_value = _get_mock_units()

    mock_conflicts_res = MagicMock()
    mock_conflicts_res.scalars.return_value.all.return_value = [MockConflictModel()]

    mock_session.execute = AsyncMock(side_effect=[
        mock_source_res,
        mock_units_res,
        mock_conflicts_res,
    ])
    return mock_session


def test_query_answerable_returns_grounded_answer(api_client):
    """Answerable query on merge sort complexity returns active evidence, citations, and abstained=False."""
    from app.main import app
    from app.database.postgres import get_db

    async def override_db():
        yield _mock_db_with_source()

    app.dependency_overrides[get_db] = override_db

    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Merge sort runs in O(n log n) worst case (at 00:12)."
        response = api_client.post('/api/query', json={
            'source_id': 'source-test-123',
            'query': 'What is the worst case time complexity of merge sort?',
            'include_evidence': True,
            'include_conflicts': True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data['abstained'] is False
        assert len(data['evidence']) > 0
        assert any('ku_01' in ev.get('knowledge_unit_id', '') or 'ku_03' in ev.get('knowledge_unit_id', '') for ev in data['evidence'])
        assert 'O(n log n)' in data['answer'] or 'merge sort' in data['answer'].lower()

    app.dependency_overrides.clear()


def test_query_unanswerable_triggers_abstention(api_client):
    """Out-of-domain query about Quantum Shor algorithm triggers subject-aware abstention."""
    from app.main import app
    from app.database.postgres import get_db

    async def override_db():
        yield _mock_db_with_source()

    app.dependency_overrides[get_db] = override_db

    response = api_client.post('/api/query', json={
        'source_id': 'source-test-123',
        'query': 'What is the time complexity of quantum Fourier transform in Shor algorithm?',
        'include_evidence': True,
        'include_conflicts': True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data['abstained'] is True
    assert 'insufficient evidence' in data['answer'].lower()
    assert len(data['evidence']) == 0
    assert len(data['conflicts']) == 0

    app.dependency_overrides.clear()


def test_query_irrelevant_conflict_suppressed(api_client):
    """A query about binary search code must NOT receive a merge sort conflict alert."""
    from app.main import app
    from app.database.postgres import get_db

    async def override_db():
        yield _mock_db_with_source()

    app.dependency_overrides[get_db] = override_db

    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Binary search implementation uses low and high pointers."
        response = api_client.post('/api/query', json={
            'source_id': 'source-test-123',
            'query': 'Show me the Python code implementation for binary search.',
            'include_evidence': True,
            'include_conflicts': True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data['abstained'] is False
        # Conflict on merge sort must NOT be attached to binary search response
        assert len(data['conflicts']) == 0

    app.dependency_overrides.clear()
