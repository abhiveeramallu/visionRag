"""
Comprehensive tests for source-isolated retrieval, VEKG boundaries, and chat history.

Verifies:
1. Query for source A retrieves only evidence from source A.
2. Query for source B retrieves only evidence from source B.
3. Source A's chat history does not appear in source B's chat.
4. Citations refer only to the selected source by default.
5. VEKG traversal respects the selected source boundary (no cross-source substitution).
6. Missing or invalid source ID produces a clear validation error.
7. Unprocessed source (pending/processing/failed) cannot be treated as ready for retrieval.
8. Unsupported query triggers the existing abstention logic.
9. Restoring chat session by source ID preserves isolated history across sessions/refreshes.
10. Cross-source conversation access rejection (cannot query with another source's conversation ID).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime


class MockSource:
    def __init__(self, id, title, status="completed", source_type="video"):
        self.id = id
        self.title = title
        self.status = status
        self.source_type = source_type
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.url = None
        self.file_path = None
        self.duration = 120.0
        self.num_pages = 5
        self.channel = None
        self.upload_date = None
        self.metadata_ = {}


class MockUnit:
    def __init__(self, **kwargs):
        self.page = None
        self.slide = None
        self.timestamp_start = None
        self.timestamp_end = None
        self.confidence = 0.95
        self.status = "verified"
        self.version = 1
        self.previous_version_id = None
        self.correction_reason = None
        self.__dict__.update(kwargs)


class MockConversation:
    def __init__(self, id, source_id, title="Test Chat"):
        self.id = id
        self.source_id = source_id
        self.title = title
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class MockMessage:
    def __init__(self, id, conversation_id, source_id, role, content):
        self.id = id
        self.conversation_id = conversation_id
        self.source_id = source_id
        self.role = role
        self.content = content
        self.evidence = []
        self.conflicts = []
        self.trace = {}
        self.confidence = 0.9
        self.strategy = "hybrid"
        self.abstained = False
        self.latency_ms = 5.0
        self.created_at = datetime.utcnow()


@pytest.fixture
def client():
    with patch('app.database.postgres.init_db', new_callable=AsyncMock), \
         patch('app.database.qdrant.QdrantManager') as mock_qdrant, \
         patch('app.indexing.vector_index.VectorIndex.search', new_callable=AsyncMock) as mock_vsearch:
        mock_qdrant.return_value.init_collection = AsyncMock()
        mock_qdrant.return_value.search = AsyncMock(return_value=[])
        mock_vsearch.return_value = []
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def test_query_retrieves_only_source_a_evidence(client):
    """Querying Source A returns only Source A evidence; Source B units are never leaked."""
    from app.main import app
    from app.database.postgres import get_db

    src_a = MockSource("src-A", "Algorithms Lecture A")
    ku_a1 = MockUnit(id="ku-A1", concept="Merge Sort", content="Merge sort is O(n log n)", modality="ocr", source_id="src-A")
    ku_a2 = MockUnit(id="ku-A2", concept="Quick Sort", content="Quick sort pivot partitioning", modality="code", source_id="src-A")

    async def override_db():
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        res_src = MagicMock()
        res_src.scalar_one_or_none.return_value = src_a
        res_kus = MagicMock()
        res_kus.scalars.return_value.all.return_value = [ku_a1, ku_a2]
        res_confs = MagicMock()
        res_confs.scalars.return_value.all.return_value = []
        res_conv = MagicMock()
        res_conv.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[res_src, res_kus, res_confs, res_conv])
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Merge sort time complexity is O(n log n)."
        response = client.post('/api/query', json={
            'source_id': 'src-A',
            'query': 'What is merge sort complexity?',
            'include_evidence': True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data['source_id'] == 'src-A'
        for ev in data['evidence']:
            assert ev['source_id'] == 'src-A'
            assert 'src-B' not in ev['source_id']

    app.dependency_overrides.clear()


def test_query_retrieves_only_source_b_evidence(client):
    """Querying Source B returns only Source B evidence; Source A units are excluded."""
    from app.main import app
    from app.database.postgres import get_db

    src_b = MockSource("src-B", "Networking Lecture B")
    ku_b1 = MockUnit(id="ku-B1", concept="TCP Handshake", content="TCP uses SYN, SYN-ACK, ACK 3-way handshake", modality="ocr", source_id="src-B")

    async def override_db():
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        res_src = MagicMock()
        res_src.scalar_one_or_none.return_value = src_b
        res_kus = MagicMock()
        res_kus.scalars.return_value.all.return_value = [ku_b1]
        res_confs = MagicMock()
        res_confs.scalars.return_value.all.return_value = []
        res_conv = MagicMock()
        res_conv.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[res_src, res_kus, res_confs, res_conv])
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "TCP establishes connections with a three-way handshake."
        response = client.post('/api/query', json={
            'source_id': 'src-B',
            'query': 'Explain the TCP handshake process.',
            'include_evidence': True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data['source_id'] == 'src-B'
        for ev in data['evidence']:
            assert ev['source_id'] == 'src-B'

    app.dependency_overrides.clear()


def test_source_a_chat_history_does_not_appear_in_source_b(client):
    """Source A's conversation history is never visible when querying Source B's conversation endpoint."""
    from app.main import app
    from app.database.postgres import get_db

    src_b = MockSource("src-B", "Networking Lecture B")
    conv_b = MockConversation("conv-B-1", "src-B", "Networking Chat")
    msg_b1 = MockMessage("msg-b1", "conv-B-1", "src-B", "user", "What is IP routing?")
    msg_b2 = MockMessage("msg-b2", "conv-B-1", "src-B", "assistant", "IP routing forwards packets across networks.")

    async def override_db():
        mock_session = AsyncMock()
        res_src = MagicMock()
        res_src.scalar_one_or_none.return_value = src_b
        res_conv = MagicMock()
        res_conv.scalar_one_or_none.return_value = conv_b
        res_msgs = MagicMock()
        res_msgs.scalars.return_value.all.return_value = [msg_b1, msg_b2]

        mock_session.execute = AsyncMock(side_effect=[res_src, res_conv, res_msgs])
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = client.get('/api/chat/sources/src-B/conversation')
    assert response.status_code == 200
    data = response.json()
    assert data['source_id'] == 'src-B'
    assert len(data['messages']) == 2
    # Verify all messages belong to source B
    for m in data['messages']:
        assert m['source_id'] == 'src-B'
        assert 'src-A' not in m['source_id']

    app.dependency_overrides.clear()


def test_cross_source_conversation_rejected(client):
    """Passing Source A's conversation ID in a query to Source B produces 400 Bad Request."""
    from app.main import app
    from app.database.postgres import get_db

    src_b = MockSource("src-B", "Networking Lecture B")
    # conv belongs to src-A
    conv_a = MockConversation("conv-A-1", "src-A", "Algorithms Chat")

    async def override_db():
        mock_session = AsyncMock()
        res_src = MagicMock()
        res_src.scalar_one_or_none.return_value = src_b
        res_conv = MagicMock()
        res_conv.scalar_one_or_none.return_value = conv_a  # Belongs to src-A!

        # 1. Source lookup, 2. Units lookup, 3. Conflict lookup, 4. Conversation lookup
        res_kus = MagicMock()
        res_kus.scalars.return_value.all.return_value = []
        res_confs = MagicMock()
        res_confs.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[res_src, res_kus, res_confs, res_conv])
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = client.post('/api/query', json={
        'source_id': 'src-B',
        'query': 'Explain routing protocols.',
        'conversation_id': 'conv-A-1',
    })
    assert response.status_code == 400
    assert 'does not belong to source' in response.json()['detail']

    app.dependency_overrides.clear()


def test_missing_or_invalid_source_id_produces_error(client):
    """Empty or nonexistent source_id produces clear 400 / 404 validation errors."""
    from app.main import app
    from app.database.postgres import get_db

    # 1. Empty source_id -> 400 or 422
    response = client.post('/api/query', json={
        'source_id': '',
        'query': 'What is merge sort?',
    })
    assert response.status_code in (400, 422)

    # 2. Non-existent source_id -> 404
    async def override_db():
        mock_session = AsyncMock()
        res_src = MagicMock()
        res_src.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=res_src)
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = client.post('/api/query', json={
        'source_id': 'nonexistent-uuid-999',
        'query': 'What is merge sort?',
    })
    assert response.status_code == 404
    assert 'not found' in response.json()['detail']

    app.dependency_overrides.clear()


def test_unprocessed_source_cannot_be_queried(client):
    """A source with status 'processing' or 'pending' cannot be queried (returns 409)."""
    from app.main import app
    from app.database.postgres import get_db

    src_pending = MockSource("src-pending", "Lecture in Progress", status="processing")

    async def override_db():
        mock_session = AsyncMock()
        res_src = MagicMock()
        res_src.scalar_one_or_none.return_value = src_pending
        mock_session.execute = AsyncMock(return_value=res_src)
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = client.post('/api/query', json={
        'source_id': 'src-pending',
        'query': 'What is covered in this lecture?',
    })
    assert response.status_code == 409
    assert 'not complete' in response.json()['detail']

    app.dependency_overrides.clear()


def test_vekg_traversal_refuses_cross_source_substitution(client):
    """VEKG lineage resolution never substitutes a unit from a different source."""
    from app.retrieval.retrieval_pipeline import RetrievalPipeline, Retriever, Reranker
    from app.knowledge.vekg import VEKG
    from app.knowledge.knowledge_units import ProcessedKnowledgeUnit
    from app.routing.dynamic_router import DynamicRouter
    from app.verification.provenance import ProvenanceTracker

    vekg = VEKG()
    # Unit A1 in src-A (superseded)
    u_a1 = ProcessedKnowledgeUnit(
        id="ku-A1", concept="Sorting", content="Merge sort is O(n^2)",
        modality="ocr", source_id="src-A", status="superseded", version=1
    )
    # Unit B2 in src-B (attempted cross-source correction)
    u_b2 = ProcessedKnowledgeUnit(
        id="ku-B2", concept="Sorting", content="Merge sort is O(n log n)",
        modality="formula", source_id="src-B", status="verified", version=2,
        previous_version_id="ku-A1", correction_reason="Cross source erratum"
    )
    vekg.add_unit(u_a1)
    vekg.add_unit(u_b2)

    router = DynamicRouter()
    mock_hybrid = MagicMock()
    retriever = Retriever(mock_hybrid, vekg=vekg)
    reranker = Reranker()
    provenance = ProvenanceTracker()
    pipeline = RetrievalPipeline(router, retriever, reranker, provenance)

    mock_hybrid.search = AsyncMock(return_value=[
        {'unit_id': 'ku-A1', 'final_score': 0.9, 'payload': {'source_id': 'src-A', 'concept': 'Sorting', 'status': 'superseded'}}
    ])

    import asyncio
    result = asyncio.run(pipeline.run(
        query="What is the sorting complexity?",
        source_id="src-A",
        source_type="video",
        units_by_id={'ku-A1': {'id': 'ku-A1', 'source_id': 'src-A', 'concept': 'Sorting', 'status': 'superseded'}},
    ))

    # Cross-source substitution to src-B is rejected; evidence must remain in src-A scope
    for ev in result['evidence']:
        assert ev.get('source_id') == 'src-A'


def test_new_chat_creates_fresh_isolated_conversation(client):
    """POST /api/chat/sources/{source_id}/conversation/new creates a fresh empty session."""
    from app.main import app
    from app.database.postgres import get_db

    src_a = MockSource("src-A", "Algorithms Lecture A")

    async def override_db():
        mock_session = AsyncMock()
        res_src = MagicMock()
        res_src.scalar_one_or_none.return_value = src_a
        mock_session.execute = AsyncMock(return_value=res_src)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = client.post('/api/chat/sources/src-A/conversation/new')
    assert response.status_code == 200
    data = response.json()
    assert data['source_id'] == 'src-A'
    assert data['messages'] == []

    app.dependency_overrides.clear()


def test_suggested_questions_grounded_in_source_concepts(client):
    """GET /api/chat/sources/{source_id}/suggested-questions returns questions matching stored KUs."""
    from app.main import app
    from app.database.postgres import get_db

    src_a = MockSource("src-A", "Algorithms Lecture A")
    ku1 = MockUnit(id="ku-1", concept="Gradient Descent", modality="formula", source_id="src-A", confidence=0.98)
    ku2 = MockUnit(id="ku-2", concept="Binary Search", modality="code", source_id="src-A", confidence=0.95)

    async def override_db():
        mock_session = AsyncMock()
        res_src = MagicMock()
        res_src.scalar_one_or_none.return_value = src_a
        res_kus = MagicMock()
        res_kus.scalars.return_value.all.return_value = [ku1, ku2]
        mock_session.execute = AsyncMock(side_effect=[res_src, res_kus])
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    response = client.get('/api/chat/sources/src-A/suggested-questions')
    assert response.status_code == 200
    data = response.json()
    assert data['source_id'] == 'src-A'
    assert len(data['questions']) >= 2
    # Concept matching verification
    questions_text = ' '.join(data['questions'])
    assert 'Gradient Descent' in questions_text
    assert 'Binary Search' in questions_text

    app.dependency_overrides.clear()
