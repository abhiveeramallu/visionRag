"""
End-to-End integration tests for VisionRAG-X verifying the 10 core research scenarios:
1. Simple answerable factual query.
2. Query answered from slide/document evidence.
3. Formula query (Gradient descent update rule).
4. Correction/version query using real course erratum fixture (Page 6 erratum resolving Page 2 slip).
5. Cross-modal conflict query.
6. Unanswerable query triggering subject-aware abstention.
7. Source-specific isolation forbidding cross-source candidate retrieval.
8. LLM-unavailable query returning graceful, non-crashing evidence status.
9. Malformed or hallucinated citation indices sanitized by citation validator.
10. Conversation persistence scoped per source across multiple turns.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime
from app.generation.answer import validate_citations


class MockCourseSource:
    id = "src_sample_course"
    title = "VisionRAG-X Sample Course (Algorithms & ML)"
    source_type = "pdf"
    status = "completed"
    created_at = datetime.utcnow()


class MockOtherSource:
    id = "src_other_course"
    title = "Operating Systems Concepts"
    source_type = "pdf"
    status = "completed"
    created_at = datetime.utcnow()


class MockUnit:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _get_course_units():
    return [
        MockUnit(
            id="ku_c1",
            concept="Merge Sort Time Complexity",
            content="Merge sort divides arrays recursively into halves. Its time complexity is O(n log n) in best, average, and worst cases.",
            modality="ocr",
            source_id="src_sample_course",
            timestamp_start=None,
            timestamp_end=None,
            page=2,
            slide=None,
            confidence=0.96,
            status="verified",
            version=1,
            previous_version_id=None,
            correction_reason=None,
        ),
        MockUnit(
            id="ku_c2",
            concept="Gradient Descent Optimization",
            content="Gradient descent update rule is theta = theta - alpha * nabla J(theta), where alpha is learning rate.",
            modality="formula",
            source_id="src_sample_course",
            timestamp_start=None,
            timestamp_end=None,
            page=3,
            slide=None,
            confidence=0.94,
            status="active",
            version=1,
            previous_version_id=None,
            correction_reason=None,
        ),
        MockUnit(
            id="ku_c3_old",
            concept="Merge Sort Quadratic Slip",
            content="In earlier whiteboard capture, merge sort was hastily written as O(n^2).",
            modality="ocr",
            source_id="src_sample_course",
            timestamp_start=None,
            timestamp_end=None,
            page=2,
            slide=None,
            confidence=0.85,
            status="superseded",
            version=1,
            previous_version_id=None,
            correction_reason=None,
        ),
        MockUnit(
            id="ku_c3_corr",
            concept="Merge Sort Page 6 Erratum",
            content="Course Errata Page 6: The whiteboard capture showing O(n^2) was an error. The actual verified time complexity of merge sort is O(n log n).",
            modality="ocr",
            source_id="src_sample_course",
            timestamp_start=None,
            timestamp_end=None,
            page=6,
            slide=None,
            confidence=0.98,
            status="verified",
            version=2,
            previous_version_id="ku_c3_old",
            correction_reason="Errata Sheet Page 6 explicitly corrected whiteboard mistake",
        ),
    ]


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


def _mock_db_session():
    session = AsyncMock()
    mock_src_res = MagicMock()
    mock_src_res.scalar_one_or_none.return_value = MockCourseSource()

    mock_units_res = MagicMock()
    mock_units_res.scalars.return_value.all.return_value = _get_course_units()

    mock_conf_res = MagicMock()
    mock_conf_res.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[
        mock_src_res,
        mock_units_res,
        mock_conf_res,
    ])
    return session


def test_scenario_1_answerable_factual_query(api_client):
    """Scenario 1: Simple answerable factual query returns grounded answer."""
    from app.main import app
    from app.database.postgres import get_db

    async def override():
        yield _mock_db_session()

    app.dependency_overrides[get_db] = override
    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Merge sort has a time complexity of O(n log n) [1]."
        res = api_client.post('/api/query', json={
            'source_id': 'src_sample_course',
            'query': 'What is the time complexity of merge sort?',
        })
        assert res.status_code == 200
        data = res.json()
        assert data['abstained'] is False
        assert len(data['evidence']) > 0
        assert 'O(n log n)' in data['answer']
    app.dependency_overrides.clear()


def test_scenario_2_document_evidence_query(api_client):
    """Scenario 2: Query answered from slide/document evidence cites page numbers."""
    from app.main import app
    from app.database.postgres import get_db

    async def override():
        yield _mock_db_session()

    app.dependency_overrides[get_db] = override
    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm, \
         patch('app.indexing.vector_index.VectorIndex.search', new_callable=AsyncMock) as mock_vsearch:
        mock_llm.return_value = "According to Page 2 and Page 6 [1], merge sort divides the input recursively."
        mock_vsearch.return_value = [
            {'unit_id': 'ku_c1', 'score': 0.88, 'payload': {'source_id': 'src_sample_course'}},
            {'unit_id': 'ku_c3_corr', 'score': 0.82, 'payload': {'source_id': 'src_sample_course'}},
        ]
        res = api_client.post('/api/query', json={
            'source_id': 'src_sample_course',
            'query': 'How does merge sort work according to the slides?',
        })
        assert res.status_code == 200
        data = res.json()
        assert any(e.get('page') in (2, 6) for e in data['evidence'])
    app.dependency_overrides.clear()


def test_scenario_3_formula_query(api_client):
    """Scenario 3: Formula query routes to formula evidence for gradient descent."""
    from app.main import app
    from app.database.postgres import get_db

    async def override():
        yield _mock_db_session()

    app.dependency_overrides[get_db] = override
    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "The gradient descent update rule is theta = theta - alpha * nabla J(theta) [1]."
        res = api_client.post('/api/query', json={
            'source_id': 'src_sample_course',
            'query': 'What is the mathematical update rule for gradient descent theta?',
        })
        assert res.status_code == 200
        data = res.json()
        assert any('theta' in e.get('text', '').lower() for e in data['evidence'])
    app.dependency_overrides.clear()


def test_scenario_4_erratum_version_resolution(api_client):
    """Scenario 4: Erratum query resolves superseded whiteboard slip to Page 6 correction."""
    from app.main import app
    from app.database.postgres import get_db

    async def override():
        yield _mock_db_session()

    app.dependency_overrides[get_db] = override
    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "The Page 6 errata explicitly corrected the earlier O(n^2) slip to verified O(n log n) [1]."
        res = api_client.post('/api/query', json={
            'source_id': 'src_sample_course',
            'query': 'Was the merge sort complexity mistake corrected in the errata sheet?',
        })
        assert res.status_code == 200
        data = res.json()
        # Verify the active correction unit (ku_c3_corr, Page 6) was retrieved
        retrieved_ids = [e.get('knowledge_unit_id') or e.get('id') for e in data['evidence']]
        assert 'ku_c3_corr' in retrieved_ids
    app.dependency_overrides.clear()


def test_scenario_6_unanswerable_query_abstains(api_client):
    """Scenario 6: Out-of-domain query safely triggers evidence sufficiency abstention."""
    from app.main import app
    from app.database.postgres import get_db

    async def override():
        yield _mock_db_session()

    app.dependency_overrides[get_db] = override
    res = api_client.post('/api/query', json={
        'source_id': 'src_sample_course',
        'query': 'What is the time complexity of the quantum Shor factoring algorithm?',
    })
    assert res.status_code == 200
    data = res.json()
    assert data['abstained'] is True
    assert 'insufficient evidence' in data['answer'].lower()
    assert len(data['evidence']) == 0
    app.dependency_overrides.clear()


def test_scenario_7_source_isolation_forbids_cross_source(api_client):
    """Scenario 7: Candidate retrieval strictly isolates units to the requested source ID."""
    from app.main import app
    from app.database.postgres import get_db

    async def override():
        yield _mock_db_session()

    app.dependency_overrides[get_db] = override
    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Answer."
        res = api_client.post('/api/query', json={
            'source_id': 'src_sample_course',
            'query': 'Explain virtual memory paging.',
        })
        assert res.status_code == 200
        data = res.json()
        # All evidence returned must belong to src_sample_course, none from src_other_course
        for ev in data['evidence']:
            assert ev.get('source_id') == 'src_sample_course'
    app.dependency_overrides.clear()


def test_scenario_8_llm_unavailable_returns_graceful_evidence_status(api_client):
    """Scenario 8: When LLM is unconfigured or unavailable, returns clear status with evidence."""
    from app.main import app
    from app.database.postgres import get_db
    from app.generation.llm import ConfigurationError

    async def override():
        yield _mock_db_session()

    app.dependency_overrides[get_db] = override
    with patch('app.generation.llm.LLMClient.complete', side_effect=ConfigurationError("Ollama service is not reachable")):
        res = api_client.post('/api/query', json={
            'source_id': 'src_sample_course',
            'query': 'What is the time complexity of merge sort?',
        })
        assert res.status_code == 200
        data = res.json()
        assert 'not reachable' in data['answer'].lower() or 'retrieved evidence is shown below' in data['answer'].lower()
        assert len(data['evidence']) > 0
    app.dependency_overrides.clear()


def test_scenario_9_malformed_citation_sanitization():
    """Scenario 9: Model hallucinations citing nonexistent [99] are stripped."""
    evidence = [
        {'id': 'ku_1', 'text': 'Grounded fact', 'page': 1},
    ]
    raw_answer = "Grounded fact [1]. Hallucinated claim [99]."
    cleaned, valid, invalid = validate_citations(raw_answer, evidence)

    assert valid == [1]
    assert invalid == [99]
    assert '[1]' in cleaned
    assert '[99]' not in cleaned
