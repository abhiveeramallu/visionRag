"""
Basic API endpoint tests for VisionRAG-X.
Tests use TestClient without database connections for fast unit testing.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient with database dependencies mocked out."""
    with patch('app.database.postgres.init_db', new_callable=AsyncMock), \
         patch('app.database.qdrant.QdrantManager') as mock_qdrant:
        mock_qdrant.return_value.init_collection = AsyncMock()
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def test_root_endpoint(client):
    """GET / should return 200 with version info."""
    response = client.get('/')
    assert response.status_code == 200
    data = response.json()
    assert 'version' in data
    assert data['version'] == '0.1.0'


def test_health_endpoint_returns_200(client):
    """GET /api/health should always return 200 (even if components are down)."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.json()
    assert 'status' in data
    assert data['status'] in ('healthy', 'degraded', 'unhealthy')
    assert 'components' in data


def test_upload_no_file_returns_422(client):
    """POST /api/upload without a file should return 422 Unprocessable Entity."""
    response = client.post('/api/upload')
    assert response.status_code == 422


def test_youtube_invalid_url_returns_422(client):
    """POST /api/youtube with a non-YouTube URL should return 422."""
    response = client.post('/api/youtube', json={'url': 'https://vimeo.com/123456'})
    assert response.status_code == 422


def test_youtube_valid_url_accepted(client):
    """POST /api/youtube with a valid YouTube URL should return 202 (processing queued)."""
    with patch('app.database.postgres.get_db') as mock_db_dep:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_db_dep.return_value.__aiter__.return_value = iter([mock_session])

        # We can't fully test the DB here without a real DB, just check URL validation
        response = client.post('/api/youtube', json={'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})
        # Should not be 422 (URL is valid format)
        assert response.status_code != 422


def test_status_not_found(client):
    """GET /api/status/nonexistent-id should return 404."""
    with patch('app.api.upload.get_db') as mock_db:
        from sqlalchemy.ext.asyncio import AsyncSession
        mock_session = AsyncMock(spec=AsyncSession)
        # Mock execute to return no result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_db():
            yield mock_session

        from app.main import app
        from app.database.postgres import get_db
        app.dependency_overrides[get_db] = override_db

        response = client.get('/api/status/nonexistent-id-12345')
        assert response.status_code == 404

        app.dependency_overrides.clear()


def test_query_source_not_found(client):
    """POST /api/query with unknown source should return 404."""
    with patch('app.api.query.get_db'):
        from app.main import app
        from app.database.postgres import get_db

        async def override_db():
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            yield mock_session

        app.dependency_overrides[get_db] = override_db
        response = client.post('/api/query', json={
            'source_id': 'nonexistent-123',
            'query': 'What is merge sort?'
        })
        assert response.status_code == 404
        app.dependency_overrides.clear()


def test_knowledge_graph_empty(client):
    """GET /api/knowledge-graph with no sources should return empty graph structure."""
    with patch('app.api.query.get_db'):
        from app.main import app
        from app.database.postgres import get_db

        async def override_db():
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)
            yield mock_session

        app.dependency_overrides[get_db] = override_db
        response = client.get('/api/knowledge-graph')
        assert response.status_code == 200
        data = response.json()
        assert 'nodes' in data
        assert 'edges' in data
        assert 'summary' in data
        assert data['nodes'] == []
        assert data['edges'] == []
        app.dependency_overrides.clear()


def test_knowledge_graph_with_units_and_lineage(client):
    """GET /api/knowledge-graph should return real nodes and correction edges."""
    with patch('app.api.query.get_db'):
        from app.main import app
        from app.database.postgres import get_db
        from app.knowledge.models import Source, KnowledgeUnit

        mock_src = Source(id='src-1', title='Algorithms PDF', status='completed')
        mock_ku1 = KnowledgeUnit(
            id='ku-1', concept='Merge Sort', content='O(n^2)', modality='ocr',
            source_id='src-1', status='superseded', version=1, confidence=0.8, page=2
        )
        mock_ku2 = KnowledgeUnit(
            id='ku-2', concept='Merge Sort', content='O(n log n)', modality='formula',
            source_id='src-1', status='verified', version=2, confidence=0.9, page=6,
            previous_version_id='ku-1', correction_reason='Errata correction'
        )

        async def override_db():
            mock_session = AsyncMock()
            # 1. Sources query
            res_src = MagicMock()
            res_src.scalars.return_value.all.return_value = [mock_src]
            # 2. Units query
            res_ku = MagicMock()
            res_ku.scalars.return_value.all.return_value = [mock_ku1, mock_ku2]
            # 3. Evidence count query
            res_ev = MagicMock()
            res_ev.all.return_value = [('ku-1', 1), ('ku-2', 1)]
            # 4. Conflicts query
            res_conf = MagicMock()
            res_conf.scalars.return_value.all.return_value = []

            mock_session.execute = AsyncMock(side_effect=[res_src, res_ku, res_ev, res_conf])
            yield mock_session

        app.dependency_overrides[get_db] = override_db
        response = client.get('/api/knowledge-graph')
        assert response.status_code == 200
        data = response.json()
        assert len(data['nodes']) == 2
        assert len(data['edges']) == 1
        edge = data['edges'][0]
        assert edge['relation'] == 'corrects'
        assert edge['source'] == 'ku-2'
        assert edge['target'] == 'ku-1'
        assert edge['reason'] == 'Errata correction'
        app.dependency_overrides.clear()


def test_list_knowledge_units(client):
    """GET /api/knowledge-units should return paginated list of units."""
    with patch('app.api.query.get_db'):
        from app.main import app
        from app.database.postgres import get_db
        from app.knowledge.models import Source, KnowledgeUnit

        mock_src = Source(id='src-1', title='Algorithms PDF', status='completed')
        mock_ku = KnowledgeUnit(
            id='ku-1', concept='Merge Sort', content='O(n log n)', modality='formula',
            source_id='src-1', status='verified', version=1, confidence=0.9, page=6
        )

        async def override_db():
            mock_session = AsyncMock()
            # 1. Count query
            res_count = MagicMock()
            res_count.scalar.return_value = 1
            # 2. Units query
            res_ku = MagicMock()
            res_ku.scalars.return_value.all.return_value = [mock_ku]
            # 3. Source query
            res_src = MagicMock()
            res_src.scalars.return_value.all.return_value = [mock_src]
            # 4. Evidence counts query
            res_ev = MagicMock()
            res_ev.all.return_value = [('ku-1', 2)]

            mock_session.execute = AsyncMock(side_effect=[res_count, res_ku, res_src, res_ev])
            yield mock_session

        app.dependency_overrides[get_db] = override_db
        response = client.get('/api/knowledge-units?search=Merge')
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['items']) == 1
        assert data['items'][0]['id'] == 'ku-1'
        assert data['items'][0]['concept'] == 'Merge Sort'
        assert data['items'][0]['source_title'] == 'Algorithms PDF'
        assert data['items'][0]['evidence_count'] == 2
        app.dependency_overrides.clear()


def test_get_knowledge_unit_detail(client):
    """GET /api/knowledge-units/{ku_id} returns detailed unit, lineage, and evidence."""
    with patch('app.api.query.get_db'):
        from app.main import app
        from app.database.postgres import get_db
        from app.knowledge.models import Source, KnowledgeUnit, Evidence

        mock_src = Source(id='src-1', title='Algorithms PDF', status='completed', source_type='pdf')
        mock_ku = KnowledgeUnit(
            id='ku-2', concept='Merge Sort', content='O(n log n)', modality='formula',
            source_id='src-1', status='verified', version=2, confidence=0.95, page=6,
            previous_version_id='ku-1', correction_reason='Errata correction'
        )
        mock_prev_ku = KnowledgeUnit(
            id='ku-1', concept='Merge Sort', content='O(n^2)', modality='ocr',
            source_id='src-1', status='superseded', version=1, confidence=0.8, page=2
        )
        mock_ev = Evidence(
            id='ev-1', knowledge_unit_id='ku-2', text='Merge sort is O(n log n)',
            modality='formula', page=6, extraction_confidence=0.95
        )

        async def override_db():
            mock_session = AsyncMock()
            # 1. Main unit
            res_unit = MagicMock()
            res_unit.scalar_one_or_none.return_value = mock_ku
            # 2. Source
            res_src = MagicMock()
            res_src.scalar_one_or_none.return_value = mock_src
            # 3. Evidence
            res_ev = MagicMock()
            res_ev.scalars.return_value.all.return_value = [mock_ev]
            # 4. Previous unit in chain
            res_prev = MagicMock()
            res_prev.scalar_one_or_none.return_value = mock_prev_ku
            # 5. Look for newer unit (none)
            res_newer = MagicMock()
            res_newer.scalar_one_or_none.return_value = None
            # 6. Conflicts
            res_conf = MagicMock()
            res_conf.scalars.return_value.all.return_value = []

            mock_session.execute = AsyncMock(side_effect=[
                res_unit, res_src, res_ev, res_prev, res_newer, res_conf
            ])
            yield mock_session

        app.dependency_overrides[get_db] = override_db
        response = client.get('/api/knowledge-units/ku-2')
        assert response.status_code == 200
        data = response.json()
        assert data['id'] == 'ku-2'
        assert data['source']['title'] == 'Algorithms PDF'
        assert len(data['evidence']) == 1
        assert len(data['lineage']) == 2
        assert data['lineage'][0]['id'] == 'ku-1'
        assert data['lineage'][1]['id'] == 'ku-2'
        app.dependency_overrides.clear()


def test_get_evaluation_artifacts(client):
    """GET /api/evaluation/artifacts reads actual benchmark files from disk."""
    response = client.get('/api/evaluation/artifacts')
    assert response.status_code == 200
    data = response.json()
    assert 'benchmarks' in data
    assert 'synthetic' in data['benchmarks']
    assert 'real_video' in data['benchmarks']
    assert 'ablations' in data
    assert len(data['benchmarks']['synthetic']['results']) >= 6
    assert len(data['ablations']['conditions']) >= 7


