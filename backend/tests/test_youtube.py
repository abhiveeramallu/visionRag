"""
Unit tests for YouTube ingestion module in VisionRAG-X.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

from app.ingestion.youtube import (
    MAX_DURATION_SECONDS,
    YouTubeIngester,
    YouTubeIngestionError,
    classify_youtube_error,
)


def test_validate_url():
    ingester = YouTubeIngester()
    assert ingester.validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert ingester.validate_url("https://youtu.be/dQw4w9WgXcQ")
    assert ingester.validate_url("https://www.youtube.com/embed/dQw4w9WgXcQ")
    assert not ingester.validate_url("https://vimeo.com/123456")
    assert not ingester.validate_url("not a url")
    assert not ingester.validate_url(None)
    assert not ingester.validate_url(12345)


def test_clean_url():
    ingester = YouTubeIngester()
    dirty_watch = "https://www.youtube.com/watch?v=MTpg1Egq6PM&list=PLR7krO3VHssS2rKksstCXwB5B13CXcQqd&index=2"
    cleaned = ingester.clean_url(dirty_watch)
    assert cleaned == "https://www.youtube.com/watch?v=MTpg1Egq6PM"

    dirty_short = "https://youtu.be/MTpg1Egq6PM?list=PLR7krO3VHssS2rKksstCXwB5B13CXcQqd"
    cleaned_short = ingester.clean_url(dirty_short)
    assert cleaned_short == "https://youtu.be/MTpg1Egq6PM"

    simple_url = "https://www.youtube.com/watch?v=abc12345"
    assert ingester.clean_url(simple_url) == "https://www.youtube.com/watch?v=abc12345"


def test_classify_youtube_error():
    url = "https://www.youtube.com/watch?v=test"

    e_priv = yt_dlp.utils.DownloadError("Private video. Sign in if you've been granted access.")
    assert "private" in classify_youtube_error(e_priv, url).lower()

    e_unavail = yt_dlp.utils.DownloadError("ERROR: [youtube] test: This video is unavailable")
    assert "unavailable" in classify_youtube_error(e_unavail, url).lower()

    e_age = yt_dlp.utils.DownloadError("Sign in to confirm your age. This video may be inappropriate")
    assert "age verification" in classify_youtube_error(e_age, url).lower()

    e_geo = yt_dlp.utils.DownloadError("The uploader has not made this video available in your country")
    assert "not available in your region" in classify_youtube_error(e_geo, url).lower()

    e_net = yt_dlp.utils.DownloadError("Failed to resolve 'www.youtube.com' ([Errno 8] nodename nor servname provided)")
    assert "network error" in classify_youtube_error(e_net, url).lower()

    e_fmt = yt_dlp.utils.DownloadError("Requested format is not available. Use --list-formats")
    assert "format could not be found" in classify_youtube_error(e_fmt, url).lower()


@pytest.mark.asyncio
async def test_fetch_metadata_duration_guard():
    ingester = YouTubeIngester()
    fake_info = {
        "title": "Super Long Video",
        "duration": MAX_DURATION_SECONDS + 100,
        "channel": "Long Channel",
        "upload_date": "20240101",
        "description": "test",
        "thumbnail": "thumb.jpg",
        "id": "long123",
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = fake_info
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        with pytest.raises(YouTubeIngestionError, match="exceeds maximum allowed"):
            await ingester.fetch_metadata("https://www.youtube.com/watch?v=long123")


@pytest.mark.asyncio
async def test_fetch_metadata_success():
    ingester = YouTubeIngester()
    fake_info = {
        "title": "Digital Electronics Lecture 1",
        "duration": 1800,
        "channel": "Prof Smith",
        "upload_date": "20240501",
        "description": "Introduction to logic gates",
        "thumbnail": "https://img.youtube.com/vi/abc/0.jpg",
        "id": "abc123",
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = fake_info
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        meta = await ingester.fetch_metadata("https://www.youtube.com/watch?v=abc123&list=testplaylist")
        assert meta["title"] == "Digital Electronics Lecture 1"
        assert meta["duration"] == 1800
        assert meta["channel"] == "Prof Smith"
        assert meta["id"] == "abc123"


@pytest.mark.asyncio
async def test_download_audio_fallback(tmp_path):
    ingester = YouTubeIngester()
    fake_meta = {
        "title": "Test Video",
        "duration": 300,
        "channel": "Test Channel",
        "upload_date": "20240101",
        "description": "",
        "thumbnail": "",
        "id": "test123",
    }

    # Simulate video file creation on disk
    def fake_video_download(*args, **kwargs):
        video_file = tmp_path / "mock_id_video.mp4"
        video_file.write_bytes(b"mock video content")

    with patch.object(ingester, "fetch_metadata", return_value=fake_meta), \
         patch("uuid.uuid4", return_value="mock_id"), \
         patch("yt_dlp.YoutubeDL") as mock_ydl_cls, \
         patch("app.ingestion.youtube._extract_audio_from_video") as mock_extract_audio:

        mock_instance = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance
        # Video download succeeds by creating the file
        mock_instance.download.side_effect = fake_video_download
        # Fallback audio extraction succeeds
        fallback_audio = tmp_path / "mock_id_audio.m4a"
        fallback_audio.write_bytes(b"mock audio content")
        mock_extract_audio.return_value = fallback_audio

        res = await ingester.download("https://www.youtube.com/watch?v=test123", tmp_path)
        assert res["file_path"] is not None
        assert Path(res["file_path"]).exists()
        assert res["title"] == "Test Video"
        assert res["duration"] == 300
