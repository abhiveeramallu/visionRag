"""
Tests for VisionRAG-X Sources API:
- Discovery of more than 4 sources
- Search filtering (including older sources)
- Pagination (limit & offset)
- File path masking and media_url assignment
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.postgres import get_db
from app.knowledge.models import Source


@pytest.fixture
def client():
    return TestClient(app)


def _create_mock_sources(count=10):
    return [
        Source(
            id=f"src-{i:03d}",
            title=f"Source Document {i:03d}" if i != 8 else "VisionRAG-X_Sample_Course.pdf",
            source_type="audio" if i % 2 == 0 else "pdf",
            file_path=f"data/uploads/src-{i:03d}/file.mp3" if i % 2 == 0 else f"data/uploads/src-{i:03d}/file.pdf",
            duration=300.0 if i % 2 == 0 else None,
            num_pages=None if i % 2 == 0 else 15,
            status="completed",
            created_at=datetime(2026, 1, 1, 10, i, 0),
        )
        for i in range(count)
    ]


def test_sources_list_returns_more_than_four(client):
    """Verify that the sources endpoint returns all available sources (more than 4)."""
    mock_sources = _create_mock_sources(count=10)

    async def override_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_sources
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session

    app.dependency_overrides[get_db] = override_db
    try:
        res = client.get("/api/sources")
        assert res.status_code == 200
        sources = res.json()
        assert isinstance(sources, list)
        assert len(sources) == 10, f"Expected 10 sources, got {len(sources)}"
        assert sources[0]["media_url"].startswith("/api/source/")
        assert sources[0]["has_media"] is True
    finally:
        app.dependency_overrides.clear()


def test_sources_search_finds_older_sources(client):
    """Verify searching for a source that is not among the top 4 most recent."""
    mock_sources = _create_mock_sources(count=10)
    matching_sources = [s for s in mock_sources if "Sample_Course" in s.title]

    async def override_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = matching_sources
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session

    app.dependency_overrides[get_db] = override_db
    try:
        res = client.get("/api/sources?search=Sample_Course")
        assert res.status_code == 200
        sources = res.json()
        assert len(sources) == 1
        assert "VisionRAG-X_Sample_Course" in sources[0]["title"]
    finally:
        app.dependency_overrides.clear()


def test_sources_pagination_limit_and_offset(client):
    """Verify pagination controls with limit and offset."""
    mock_sources = _create_mock_sources(count=10)
    paged = mock_sources[3:6]

    async def override_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = paged
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session

    app.dependency_overrides[get_db] = override_db
    try:
        res = client.get("/api/sources?limit=3&offset=3")
        assert res.status_code == 200
        sources = res.json()
        assert len(sources) == 3
        assert sources[0]["id"] == "src-003"
    finally:
        app.dependency_overrides.clear()


def test_source_detail_masks_filepath_and_provides_media_url(client):
    """Verify that source detail endpoint masks server file_path and exposes safe media_url."""
    src = Source(
        id="src-secret-123",
        title="Sensitive Course.pdf",
        source_type="pdf",
        file_path="/var/secrets/sensitive_file.pdf",
        status="completed",
        duration=None,
        num_pages=20,
    )

    async def override_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = src
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session

    app.dependency_overrides[get_db] = override_db
    try:
        res = client.get(f"/api/source/{src.id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == src.id
        assert data.get("file_path") is None, "Server filesystem paths must never be exposed"
        assert data.get("media_url") == f"/api/source/{src.id}/media"
        assert data.get("has_media") is True
    finally:
        app.dependency_overrides.clear()
