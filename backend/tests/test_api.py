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
