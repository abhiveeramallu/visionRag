"""
Unit and integration tests for Multi-Strategy Search & Knowledge Base in VisionRAG-X:
- Semantic Search (Vector) with fault-tolerant fallback
- Keyword Search (BM25) with exact match and formula symbol preservation
- Knowledge Graph (VEKG) traversal for connected concepts & corrections
- Timestamp / Temporal Search with time-string parsing and temporal ranking
- Hybrid Search fusion
- Source Isolation vs Multi-Source (Global Knowledge Base) querying
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.routing.dynamic_router import DynamicRouter
from app.indexing.lexical_index import LexicalIndex, _tokenize
from app.indexing.hybrid_index import HybridIndex
from app.knowledge.vekg import VEKG
from app.knowledge.knowledge_units import ProcessedKnowledgeUnit
from app.retrieval.retrieval_pipeline import (
    _extract_temporal_targets,
    Retriever,
    Reranker,
    RetrievalPipeline,
)
from app.verification.provenance import ProvenanceTracker


# ---------------------------------------------------------------------------
# 1. Dynamic Router & Strategy Overrides
# ---------------------------------------------------------------------------

def test_dynamic_router_heuristic_routing():
    router = DynamicRouter()

    # Formula/math query
    r_formula = router.route("What is the formula for O(n log n)?")
    assert r_formula['strategy'] in ('formula_priority', 'lexical_only', 'hybrid')

    # Timestamp query
    r_time = router.route("What happens at 05:15 in the video?")
    assert r_time['strategy'] == 'timestamp_aware'

    # Code query
    r_code = router.route("Show me the python implementation function for merge sort")
    assert r_code['strategy'] in ('code_priority', 'hybrid')

    # General conceptual query
    r_concept = router.route("Explain the core concept of backpropagation")
    assert r_concept['strategy'] in ('hybrid', 'conceptual', 'semantic_only')


def test_dynamic_router_explicit_overrides():
    router = DynamicRouter()

    # User explicitly requested semantic
    r1 = router.route("What is the formula for O(n)?", requested_strategy="semantic")
    assert r1['strategy'] == 'semantic_only'
    assert 'User selected explicit strategy' in r1['explanation']

    # User explicitly requested keyword
    r2 = router.route("Explain neural networks", requested_strategy="keyword")
    assert r2['strategy'] == 'lexical_only'
    assert 'User selected explicit strategy' in r2['explanation']

    # User explicitly requested graph
    r3 = router.route("What happens at 02:00?", requested_strategy="graph")
    assert r3['strategy'] == 'knowledge_graph'

    # User explicitly requested timestamp
    r4 = router.route("General summary", requested_strategy="timestamp")
    assert r4['strategy'] == 'timestamp_aware'

    # User explicitly requested hybrid
    r5 = router.route("Exact match", requested_strategy="hybrid")
    assert r5['strategy'] == 'hybrid'


# ---------------------------------------------------------------------------
# 2. Lexical Index (BM25) Preserving Technical & Formula Terms
# ---------------------------------------------------------------------------

def test_lexical_index_tokenization_and_formula_preservation():
    idx = LexicalIndex()
    # Preserves single-letter math variables like n, x, y, k, etc.
    tokens = _tokenize("Complexity is O(n) where n represents input size")
    assert 'n' in tokens
    assert 'o' in tokens
    assert 'complexity' in tokens

    # Builds index and scores documents with exact keyword & phrase boost
    docs = [
        {'id': 'u1', 'concept': 'Time Complexity', 'content': 'The time complexity of quicksort is O(n log n) in average case.'},
        {'id': 'u2', 'concept': 'Merge Sort', 'content': 'Merge sort operates in divide and conquer fashion.'},
    ]
    idx.build_index(docs)

    results = idx.search("O(n log n)")
    assert len(results) > 0
    assert results[0]['unit_id'] == 'u1'
    assert results[0]['score'] > 0.0


# ---------------------------------------------------------------------------
# 3. VEKG Knowledge Graph Traversal
# ---------------------------------------------------------------------------

def test_vekg_concept_and_correction_traversal():
    vekg = VEKG()
    u1 = ProcessedKnowledgeUnit(
        id='ku_erroneous',
        concept='Merge Sort Complexity',
        content='Merge sort has worst case O(n^2).',
        modality='asr',
        source_id='src_1',
        status='superseded',
    )
    u2 = ProcessedKnowledgeUnit(
        id='ku_corrected',
        concept='Merge Sort Complexity',
        content='Erratum correction: merge sort worst case is strictly O(n log n).',
        modality='asr',
        source_id='src_1',
        status='active',
        previous_version_id='ku_erroneous',
        correction_reason='Instructor correction in subsequent slide',
    )
    u3 = ProcessedKnowledgeUnit(
        id='ku_unrelated',
        concept='Photosynthesis',
        content='Chlorophyll absorbs sunlight in plants.',
        modality='text',
        source_id='src_1',
        status='active',
    )

    vekg.reconstruct_from_units([u1, u2, u3])

    # Traverse graph for "merge sort"
    matches = vekg.traverse_related_concepts("What is merge sort complexity?", source_id='src_1')
    assert len(matches) > 0
    matched_ids = [m['unit'].id for m in matches]
    assert 'ku_corrected' in matched_ids
    assert 'ku_unrelated' not in matched_ids


# ---------------------------------------------------------------------------
# 4. Temporal Extraction & Ranking
# ---------------------------------------------------------------------------

def test_temporal_target_extraction():
    # MM:SS
    t1 = _extract_temporal_targets("What was discussed at 05:15?")
    assert t1['target_sec'] == 315.0

    # HH:MM:SS
    t2 = _extract_temporal_targets("Explain the slide at 01:20:30")
    assert t2['target_sec'] == 4830.0

    # Minutes
    t3 = _extract_temporal_targets("Jump to minute 14 in the recording")
    assert t3['target_sec'] == 840.0

    # Page
    t4 = _extract_temporal_targets("See theorem on page 42")
    assert t4['page'] == 42


@pytest.mark.asyncio
async def test_retriever_timestamp_proximity_boost():
    # Setup mock hybrid index
    hybrid_mock = MagicMock()
    hybrid_mock.search = AsyncMock(return_value=[
        {'unit_id': 'u_early', 'final_score': 0.5, 'payload': {}},
        {'unit_id': 'u_target', 'final_score': 0.5, 'payload': {}},
        {'unit_id': 'u_late', 'final_score': 0.5, 'payload': {}},
    ])

    units_by_id = {
        'u_early': {'id': 'u_early', 'source_id': 's1', 'timestamp_start': 60.0, 'timestamp_end': 90.0, 'content': 'intro'},
        'u_target': {'id': 'u_target', 'source_id': 's1', 'timestamp_start': 300.0, 'timestamp_end': 330.0, 'content': 'target discussion'},
        'u_late': {'id': 'u_late', 'source_id': 's1', 'timestamp_start': 900.0, 'timestamp_end': 930.0, 'content': 'outro'},
    }

    retriever = Retriever(hybrid_index=hybrid_mock)
    # Query at 05:15 (315 seconds) -> should boost u_target directly
    results = await retriever.retrieve(
        query="What happened at 05:15?",
        source_id="s1",
        strategy="timestamp_aware",
        units_by_id=units_by_id,
    )

    target_res = next(r for r in results if r['unit_id'] == 'u_target')
    early_res = next(r for r in results if r['unit_id'] == 'u_early')

    assert target_res.get('temporal_exact') is True
    assert target_res['final_score'] > early_res['final_score']


# ---------------------------------------------------------------------------
# 5. Hybrid Index BM25 Fallback when Vector Search Fails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hybrid_index_graceful_bm25_fallback():
    # Mock vector index to raise exception (e.g. Qdrant unreachable)
    vector_mock = MagicMock()
    vector_mock.search = AsyncMock(side_effect=Exception("Qdrant connection refused"))

    # Real lexical index
    lexical = LexicalIndex()
    docs = [{'id': 'doc1', 'concept': 'Backtracking', 'content': 'Backtracking explores solution space systematically.'}]
    lexical.build_index(docs)

    hybrid = HybridIndex(vector_mock, lexical)
    results = await hybrid.search(
        query="Backtracking solution space",
        source_id=None,
        strategy="hybrid",
        units_by_id={'doc1': docs[0]},
    )

    assert len(results) > 0
    assert results[0]['unit_id'] == 'doc1'
    assert results[0]['lexical_score'] > 0.0


# ---------------------------------------------------------------------------
# 6. Source Isolation vs Multi-Source Search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_source_isolation_in_retrieval_pipeline():
    router = DynamicRouter()
    hybrid_mock = MagicMock()
    # Hybrid search returns units from both source_A and source_B
    hybrid_mock.search = AsyncMock(return_value=[
        {'unit_id': 'u_a', 'final_score': 0.9, 'payload': {'source_id': 'src_a'}},
        {'unit_id': 'u_b', 'final_score': 0.85, 'payload': {'source_id': 'src_b'}},
    ])
    retriever = Retriever(hybrid_index=hybrid_mock)
    reranker = Reranker()
    provenance = ProvenanceTracker()
    pipeline = RetrievalPipeline(router, retriever, reranker, provenance)

    units_by_id = {
        'u_a': {'id': 'u_a', 'source_id': 'src_a', 'content': 'Source A content on recursion', 'concept': 'Recursion'},
        'u_b': {'id': 'u_b', 'source_id': 'src_b', 'content': 'Source B content on recursion', 'concept': 'Recursion'},
    }

    # Case 1: Strictly isolated to src_a
    res_isolated = await pipeline.run(
        query="Explain recursion",
        source_id="src_a",
        source_type="video",
        units_by_id=units_by_id,
    )
    for ev in res_isolated['evidence']:
        assert ev['source_id'] == 'src_a', f"Source isolation violated! Found {ev['source_id']}"

    # Case 2: Multi-source search across all sources (source_id=None or 'all')
    res_all = await pipeline.run(
        query="Explain recursion",
        source_id=None,
        source_type="mixed",
        units_by_id=units_by_id,
    )
    source_ids = {ev['source_id'] for ev in res_all['evidence']}
    assert 'src_a' in source_ids or 'src_b' in source_ids


# ---------------------------------------------------------------------------
# 7. API Endpoints & Multi-Source Routing
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from unittest.mock import patch


class MockSource:
    def __init__(self, id, title, status="completed", source_type="video"):
        self.id = id
        self.title = title
        self.status = status
        self.source_type = source_type


class MockUnit:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 'u1')
        self.concept = kwargs.get('concept', '')
        self.content = kwargs.get('content', '')
        self.modality = kwargs.get('modality', 'text')
        self.source_id = kwargs.get('source_id', 's1')
        self.timestamp_start = kwargs.get('timestamp_start')
        self.timestamp_end = kwargs.get('timestamp_end')
        self.page = kwargs.get('page')
        self.slide = kwargs.get('slide')
        self.confidence = kwargs.get('confidence', 0.95)
        self.status = kwargs.get('status', 'active')
        self.version = kwargs.get('version', 1)
        self.previous_version_id = kwargs.get('previous_version_id')
        self.correction_reason = kwargs.get('correction_reason')


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


def test_api_multi_source_query(client):
    from app.main import app
    from app.database.postgres import get_db

    src1 = MockSource("src-1", "Source One Lecture")
    src2 = MockSource("src-2", "Source Two Reading")
    u1 = MockUnit(id="u1", concept="Sorting", content="Sorting arranges elements in order.", modality="ocr", source_id="src-1")
    u2 = MockUnit(id="u2", concept="Sorting", content="Quicksort divides and conquers.", modality="ocr", source_id="src-2")

    async def override_db():
        mock_session = AsyncMock()
        res_srcs = MagicMock()
        res_srcs.scalars.return_value.all.return_value = [src1, src2]
        res_kus = MagicMock()
        res_kus.scalars.return_value.all.return_value = [u1, u2]
        res_confs = MagicMock()
        res_confs.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[res_srcs, res_kus, res_confs])
        yield mock_session

    app.dependency_overrides[get_db] = override_db

    with patch('app.generation.llm.LLMClient.complete', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Sorting can be achieved with quicksort or mergesort."
        response = client.post('/api/query', json={
            'source_id': 'all',
            'query': 'What is sorting?',
            'strategy': 'keyword',
            'include_evidence': True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data['source_id'] == 'all'
        assert data['retrieval_strategy_used'] == 'lexical_only'
        assert len(data['evidence']) > 0

    app.dependency_overrides.clear()


def test_api_virtual_endpoints_for_all_sources(client):
    # conversation
    r_conv = client.get('/api/chat/sources/all/conversation')
    assert r_conv.status_code == 200
    assert r_conv.json()['source_id'] == 'all'

    # suggested questions
    r_sq = client.get('/api/chat/sources/all/suggested-questions')
    assert r_sq.status_code == 200
    assert len(r_sq.json()['questions']) > 0

    # conversations list
    r_list = client.get('/api/chat/sources/all/conversations')
    assert r_list.status_code == 200
    assert r_list.json() == []
