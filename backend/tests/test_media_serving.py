"""
Tests for VisionRAG-X Media Serving & HTTP Range Requests.
Tests real audio (MP3), video (MP4), PDF, and PPTX file streaming, range slicing,
seeking headers, and traversal security.
"""
import os
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.postgres import get_db
from app.knowledge.models import Source

REAL_MP3_PATH = "backend/data/uploads/f7e46f40-f334-4e72-83a3-36e522b7ed20/Masters of Enterprise - 01.mp3"
REAL_VIDEO_PATH = "backend/data/uploads/cd201cc7-7002-4695-80d9-c33b72c7a2a9/vidssave.com 6 Introduction to Backtracking - Brute Force Approach 720P.mp4"
REAL_PDF_PATH = "data/samples/VisionRAG-X_Sample_Course.pdf"
REAL_PPTX_PATH = "backend/data/uploads/ec97bf29-307e-4a8c-9279-32355ffcd556/Deepfake_Digital_Forensics_Case_Study_10_Slides.pptx"


@pytest.fixture
def client():
    return TestClient(app)


def _setup_mock_source(src: Source):
    async def override_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = src
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session
    app.dependency_overrides[get_db] = override_db


def test_real_mp3_media_stream_and_headers(client):
    """Verify playing a valid MP3 through the actual media endpoint with correct MIME type."""
    src = Source(
        id="src-mp3-test",
        title="Masters of Enterprise - 01.mp3",
        source_type="audio",
        file_path=REAL_MP3_PATH,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        res = client.get(f"/api/source/{src.id}/media")
        assert res.status_code == 200
        assert res.headers.get("content-type") == "audio/mpeg"
        assert res.headers.get("accept-ranges") == "bytes"
        assert int(res.headers.get("content-length", 0)) > 1000000
    finally:
        app.dependency_overrides.clear()


def test_mp3_range_request_seeking(client):
    """Verify seeking within audio when range requests are supported (HTTP 206 Partial Content)."""
    src = Source(
        id="src-mp3-test",
        title="Masters of Enterprise - 01.mp3",
        source_type="audio",
        file_path=REAL_MP3_PATH,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        # Request bytes 1024-2047 (1024 bytes)
        headers = {"Range": "bytes=1024-2047"}
        res = client.get(f"/api/source/{src.id}/media", headers=headers)
        assert res.status_code == 206
        assert len(res.content) == 1024
        assert res.headers.get("content-type") == "audio/mpeg"
        assert res.headers.get("content-range", "").startswith("bytes 1024-2047/")
    finally:
        app.dependency_overrides.clear()


def test_mp3_range_request_large_seek(client):
    """Verify seeking far into the audio file (e.g. 5MB offset)."""
    src = Source(
        id="src-mp3-test",
        title="Masters of Enterprise - 01.mp3",
        source_type="audio",
        file_path=REAL_MP3_PATH,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        headers = {"Range": "bytes=5000000-5002047"}
        res = client.get(f"/api/source/{src.id}/media", headers=headers)
        assert res.status_code == 206
        assert len(res.content) == 2048
        assert res.headers.get("content-range", "").startswith("bytes 5000000-5002047/")
    finally:
        app.dependency_overrides.clear()


def test_mp3_invalid_range_returns_416(client):
    """Verify out-of-bounds or invalid range returns HTTP 416."""
    src = Source(
        id="src-mp3-test",
        title="Masters of Enterprise - 01.mp3",
        source_type="audio",
        file_path=REAL_MP3_PATH,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        headers = {"Range": "bytes=999999999-9999999999"}
        res = client.get(f"/api/source/{src.id}/media", headers=headers)
        assert res.status_code == 416
        assert "content-range" in res.headers
    finally:
        app.dependency_overrides.clear()


def test_video_media_range_seeking(client):
    """Verify video preview and range seeking for a supported MP4 video."""
    src = Source(
        id="src-video-test",
        title="Backtracking.mp4",
        source_type="video",
        file_path=REAL_VIDEO_PATH,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        headers = {"Range": "bytes=0-4095"}
        res = client.get(f"/api/source/{src.id}/media", headers=headers)
        assert res.status_code == 206
        assert len(res.content) == 4096
        assert res.headers.get("content-type") == "video/mp4"
        assert res.headers.get("content-range", "").startswith("bytes 0-4095/")
    finally:
        app.dependency_overrides.clear()


def test_pdf_media_stream(client):
    """Verify PDF preview document serving."""
    src = Source(
        id="src-pdf-test",
        title="VisionRAG-X_Sample_Course.pdf",
        source_type="pdf",
        file_path=REAL_PDF_PATH,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        res = client.get(f"/api/source/{src.id}/media")
        assert res.status_code == 200
        assert res.headers.get("content-type") == "application/pdf"
        assert int(res.headers.get("content-length", 0)) > 5000
    finally:
        app.dependency_overrides.clear()


def test_pptx_media_stream(client):
    """Verify PPTX presentation serving."""
    src = Source(
        id="src-pptx-test",
        title="Deepfake.pptx",
        source_type="ppt",
        file_path=REAL_PPTX_PATH,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        res = client.get(f"/api/source/{src.id}/media")
        assert res.status_code == 200
        assert "presentation" in res.headers.get("content-type", "").lower() or "officedocument" in res.headers.get("content-type", "").lower()
    finally:
        app.dependency_overrides.clear()


def test_head_media_request(client):
    """Verify HEAD request for audio media headers."""
    src = Source(
        id="src-mp3-test",
        title="Masters of Enterprise - 01.mp3",
        source_type="audio",
        file_path=REAL_MP3_PATH,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        res = client.head(f"/api/source/{src.id}/media")
        assert res.status_code == 200
        assert res.headers.get("content-type") == "audio/mpeg"
        assert res.headers.get("accept-ranges") == "bytes"
        assert int(res.headers.get("content-length", 0)) > 0
    finally:
        app.dependency_overrides.clear()


def test_non_existent_source_returns_404(client):
    """Verify non-existent source ID returns 404."""
    _setup_mock_source(None)
    try:
        res = client.get("/api/source/non-existent-source-id-12345/media")
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_youtube_source_media_returns_400(client):
    """Verify YouTube sources with no local file return 400 with helpful explanation."""
    src = Source(
        id="src-yt-test",
        title="YouTube Lecture",
        source_type="youtube",
        url="https://www.youtube.com/watch?v=12345",
        file_path=None,
        status="completed",
    )
    _setup_mock_source(src)
    try:
        res = client.get(f"/api/source/{src.id}/media")
        assert res.status_code == 400
        assert "YouTube" in res.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_cross_source_media_protection(client):
    """Verify that source media cannot be accessed with path traversal."""
    src = Source(
        id="src-traversal-test",
        title="Illegal Path Source",
        source_type="audio",
        file_path="../../../../../etc/passwd",
        status="completed",
    )
    _setup_mock_source(src)
    try:
        res = client.get(f"/api/source/{src.id}/media")
        assert res.status_code in (403, 404)
    finally:
        app.dependency_overrides.clear()
