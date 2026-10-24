"""
Unit tests for the VisionExtractor module.
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.extraction.vision import VisionExtractor


@pytest.fixture
def unconfigured_settings(mock_settings):
    import copy
    s = copy.copy(mock_settings)
    s.vision_model = ''
    return s


@pytest.fixture
def configured_settings(mock_settings):
    import copy
    s = copy.copy(mock_settings)
    s.vision_model = 'gpt-4o'
    s.llm_provider = 'openai'
    s.openai_api_key = 'test-key'
    return s


def test_vision_not_configured(unconfigured_settings):
    ve = VisionExtractor(unconfigured_settings)
    assert not ve.is_configured


def test_vision_configured(configured_settings):
    ve = VisionExtractor(configured_settings)
    assert ve.is_configured


@pytest.mark.asyncio
async def test_describe_frame_unconfigured_returns_none(unconfigured_settings, tmp_path):
    dummy_img = tmp_path / "frame.jpg"
    dummy_img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
    ve = VisionExtractor(unconfigured_settings)
    res = await ve.describe_frame(dummy_img, "src-1", timestamp=10.0)
    assert res is None


@pytest.mark.asyncio
async def test_describe_frames_unconfigured_returns_empty(unconfigured_settings):
    ve = VisionExtractor(unconfigured_settings)
    res = await ve.describe_frames([{"frame_path": "/fake/frame.jpg", "timestamp": 5.0}], "src-1")
    assert res == []


@pytest.mark.asyncio
async def test_describe_frame_nonexistent_file_returns_none(configured_settings):
    ve = VisionExtractor(configured_settings)
    res = await ve.describe_frame(Path("/nonexistent/file.jpg"), "src-1", timestamp=10.0)
    assert res is None


@pytest.mark.asyncio
async def test_describe_frame_mock_openai(configured_settings, tmp_path):
    dummy_img = tmp_path / "frame.jpg"
    dummy_img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    mock_client = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Diagram showing binary search tree balance factor."
    mock_response = MagicMock(choices=[mock_choice])
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        ve = VisionExtractor(configured_settings)
        res = await ve.describe_frame(dummy_img, "src-1", timestamp=12.5)

        assert res is not None
        assert res["modality"] == "vision"
        assert res["timestamp_start"] == 12.5
        assert "binary search tree" in res["text"]
        assert res["confidence"] == 0.85
        assert res["raw_output"]["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_health_check(configured_settings, unconfigured_settings):
    ve_on = VisionExtractor(configured_settings)
    h_on = await ve_on.health_check()
    assert h_on["available"] is True
    assert h_on["model"] == "gpt-4o"

    ve_off = VisionExtractor(unconfigured_settings)
    h_off = await ve_off.health_check()
    assert h_off["available"] is False
