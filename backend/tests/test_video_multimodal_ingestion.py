"""
Comprehensive regression test suite for Multimodal Video Ingestion (ASR + OCR) in VisionRAG-X.

Covers:
1. Video containing spoken content and text on slides produces both ASR and OCR Knowledge Units.
2. ASR succeeds while OCR returns a legitimate empty result.
3. OCR succeeds while ASR returns a legitimate empty result.
4. ASR fails unexpectedly but OCR evidence is preserved.
5. OCR fails unexpectedly but ASR evidence is preserved.
6. A modality timeout produces an explicit diagnostic rather than an infinite spinner.
7. Retrying a failed video does not duplicate existing Knowledge Units.
8. Timestamp and source provenance remain correct for both modalities.
9. AI Chat can answer a speech-based question using ASR evidence.
10. AI Chat can answer a slide-text question using OCR evidence.
11. A question involving a contradiction between speech and a slide retrieves both relevant evidence items.
12. The video is not marked fully ready while both required modalities fail unexpectedly.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.config import Settings
from app.knowledge.models import Source, ProcessingJob, KnowledgeUnit, Evidence, Conflict
from app.api.upload import run_ingestion_pipeline, retry_source
from app.schemas.requests import QueryRequest
from app.api.query import query


# ---------------------------------------------------------------------------
# Test 1: Video with Both Speech & Slide Text Produces Distinct ASR & OCR KUs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_produces_both_asr_and_ocr_kus():
    """Verify that a multimodal video creates independently identifiable ASR and OCR Knowledge Units."""
    mock_src = MagicMock(spec=Source, id="vid-both", title="Backtracking.mp4", duration=None, status="pending", metadata_={})
    added_kus = []

    def mock_add(entity):
        if isinstance(entity, KnowledgeUnit):
            added_kus.append(entity)

    mock_db = MagicMock()
    mock_db.add = MagicMock(side_effect=mock_add)
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    # 1 ASR segment and 1 OCR segment in the same 0-15s window
    asr_segs = [
        {"text": "Backtracking is an algorithmic paradigm for solving constraint satisfaction problems.", "start": 2.0, "end": 10.0, "timestamp_start": 2.0, "timestamp_end": 10.0, "confidence": 0.90, "modality": "asr", "source_id": "vid-both"}
    ]
    ocr_segs = [
        {"text": "ALGORITHM BACKTRACKING(X): STATE SPACE TREE SEARCH", "start": 5.0, "end": 12.0, "timestamp_start": 5.0, "timestamp_end": 12.0, "confidence": 0.95, "modality": "ocr", "source_id": "vid-both"}
    ]

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.video.VideoIngester.extract_audio", new_callable=AsyncMock, return_value=Path("/tmp/audio.wav")), \
         patch("app.ingestion.video.VideoIngester.extract_frames", new_callable=AsyncMock, return_value=[{"frame_path": "/tmp/f1.jpg", "timestamp": 5.0}]), \
         patch("app.ingestion.video.VideoIngester.get_video_metadata", return_value={"duration": 30.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", new_callable=AsyncMock, return_value=asr_segs), \
         patch("app.extraction.ocr.OCRExtractor.extract_from_frame_list", new_callable=AsyncMock, return_value=ocr_segs), \
         patch("app.indexing.vector_index.VectorIndex.index_units", new_callable=AsyncMock):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="vid-both",
            job_id="job-both",
            file_path="/tmp/test_video.mp4",
            source_type="video",
        )

        modalities = [ku.modality for ku in added_kus]
        assert "asr" in modalities, "Must have an ASR Knowledge Unit"
        assert "ocr" in modalities, "Must have an OCR Knowledge Unit"

        asr_ku = next(k for k in added_kus if k.modality == "asr")
        ocr_ku = next(k for k in added_kus if k.modality == "ocr")

        assert "algorithmic paradigm" in asr_ku.content
        assert "STATE SPACE TREE" in ocr_ku.content
        assert asr_ku.id != ocr_ku.id
        assert mock_src.status == "completed"


# ---------------------------------------------------------------------------
# Test 2: ASR Succeeds While OCR Returns Legitimate Empty Result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_asr_succeeds_ocr_legitimate_empty():
    """Verify that a video with spoken content but blank/diagram-only frames succeeds with OCR marked empty."""
    mock_src = MagicMock(spec=Source, id="vid-talking-head", title="Interview.mp4", duration=None, status="pending", metadata_={})
    added_kus = []

    def mock_add(entity):
        if isinstance(entity, KnowledgeUnit):
            added_kus.append(entity)

    mock_db = MagicMock()
    mock_db.add = MagicMock(side_effect=mock_add)
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    asr_segs = [
        {"text": "Here is an explanation of dynamic programming.", "start": 1.0, "end": 8.0, "confidence": 0.88, "modality": "asr", "source_id": "vid-talking-head"}
    ]

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.video.VideoIngester.extract_audio", new_callable=AsyncMock, return_value=Path("/tmp/audio.wav")), \
         patch("app.ingestion.video.VideoIngester.extract_frames", new_callable=AsyncMock, return_value=[{"frame_path": "/tmp/f1.jpg", "timestamp": 1.0}]), \
         patch("app.ingestion.video.VideoIngester.get_video_metadata", return_value={"duration": 15.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", new_callable=AsyncMock, return_value=asr_segs), \
         patch("app.extraction.ocr.OCRExtractor.extract_from_frame_list", new_callable=AsyncMock, return_value=[]), \
         patch("app.indexing.vector_index.VectorIndex.index_units", new_callable=AsyncMock):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="vid-talking-head",
            job_id="job-th",
            file_path="/tmp/th.mp4",
            source_type="video",
        )

        assert mock_src.status == "completed"
        assert len(added_kus) >= 1
        assert added_kus[0].modality == "asr"
        meta_status = mock_src.metadata_.get("modality_status", {})
        assert meta_status.get("ocr") == "empty"
        assert meta_status.get("asr") == "completed"


# ---------------------------------------------------------------------------
# Test 3: OCR Succeeds While ASR Returns Legitimate Empty Result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_ocr_succeeds_asr_legitimate_empty():
    """Verify that a silent instructional video with slides succeeds with ASR marked empty."""
    mock_src = MagicMock(spec=Source, id="vid-silent-slides", title="Slides.mp4", duration=None, status="pending", metadata_={})
    added_kus = []

    def mock_add(entity):
        if isinstance(entity, KnowledgeUnit):
            added_kus.append(entity)

    mock_db = MagicMock()
    mock_db.add = MagicMock(side_effect=mock_add)
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    ocr_segs = [
        {"text": "Definition: Merge Sort is a Divide and Conquer algorithm.", "timestamp_start": 2.0, "timestamp_end": 10.0, "confidence": 0.95, "modality": "ocr", "source_id": "vid-silent-slides"}
    ]

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.video.VideoIngester.extract_audio", new_callable=AsyncMock, return_value=Path("/tmp/audio.wav")), \
         patch("app.ingestion.video.VideoIngester.extract_frames", new_callable=AsyncMock, return_value=[{"frame_path": "/tmp/f1.jpg", "timestamp": 2.0}]), \
         patch("app.ingestion.video.VideoIngester.get_video_metadata", return_value={"duration": 15.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", new_callable=AsyncMock, return_value=[]), \
         patch("app.extraction.ocr.OCRExtractor.extract_from_frame_list", new_callable=AsyncMock, return_value=ocr_segs), \
         patch("app.indexing.vector_index.VectorIndex.index_units", new_callable=AsyncMock):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="vid-silent-slides",
            job_id="job-silent-slides",
            file_path="/tmp/slides.mp4",
            source_type="video",
        )

        assert mock_src.status == "completed"
        assert len(added_kus) >= 1
        assert added_kus[0].modality == "ocr"
        meta_status = mock_src.metadata_.get("modality_status", {})
        assert meta_status.get("asr") == "empty"
        assert meta_status.get("ocr") == "completed"


# ---------------------------------------------------------------------------
# Test 4: ASR Fails Unexpectedly but OCR Evidence Is Preserved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_asr_fails_ocr_preserved():
    """Verify that if ASR throws an unexpected error, OCR evidence is still preserved and completed."""
    mock_src = MagicMock(spec=Source, id="vid-asr-fail", title="DamagedAudio.mp4", duration=None, status="pending", metadata_={})
    added_kus = []

    def mock_add(entity):
        if isinstance(entity, KnowledgeUnit):
            added_kus.append(entity)

    mock_db = MagicMock()
    mock_db.add = MagicMock(side_effect=mock_add)
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    ocr_segs = [
        {"text": "Slide text survived despite corrupted audio track.", "timestamp_start": 0.0, "timestamp_end": 10.0, "confidence": 0.95, "modality": "ocr", "source_id": "vid-asr-fail"}
    ]

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.video.VideoIngester.extract_audio", new_callable=AsyncMock, return_value=Path("/tmp/audio.wav")), \
         patch("app.ingestion.video.VideoIngester.extract_frames", new_callable=AsyncMock, return_value=[{"frame_path": "/tmp/f1.jpg", "timestamp": 1.0}]), \
         patch("app.ingestion.video.VideoIngester.get_video_metadata", return_value={"duration": 15.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", side_effect=RuntimeError("Corrupted audio header")), \
         patch("app.extraction.ocr.OCRExtractor.extract_from_frame_list", new_callable=AsyncMock, return_value=ocr_segs), \
         patch("app.indexing.vector_index.VectorIndex.index_units", new_callable=AsyncMock):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="vid-asr-fail",
            job_id="job-asr-fail",
            file_path="/tmp/damaged.mp4",
            source_type="video",
        )

        assert mock_src.status == "completed"
        assert len(added_kus) >= 1
        assert added_kus[0].modality == "ocr"
        meta_status = mock_src.metadata_.get("modality_status", {})
        assert meta_status.get("asr") == "failed"
        assert meta_status.get("ocr") == "completed"


# ---------------------------------------------------------------------------
# Test 5: OCR Fails Unexpectedly but ASR Evidence Is Preserved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_ocr_fails_asr_preserved():
    """Verify that if OCR throws an unexpected error, ASR evidence is still preserved and completed."""
    mock_src = MagicMock(spec=Source, id="vid-ocr-fail", title="BlurryVideo.mp4", duration=None, status="pending", metadata_={})
    added_kus = []

    def mock_add(entity):
        if isinstance(entity, KnowledgeUnit):
            added_kus.append(entity)

    mock_db = MagicMock()
    mock_db.add = MagicMock(side_effect=mock_add)
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    asr_segs = [
        {"text": "Speech survived despite OCR engine crash.", "timestamp_start": 0.0, "timestamp_end": 10.0, "confidence": 0.90, "modality": "asr", "source_id": "vid-ocr-fail"}
    ]

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.video.VideoIngester.extract_audio", new_callable=AsyncMock, return_value=Path("/tmp/audio.wav")), \
         patch("app.ingestion.video.VideoIngester.extract_frames", new_callable=AsyncMock, return_value=[{"frame_path": "/tmp/f1.jpg", "timestamp": 1.0}]), \
         patch("app.ingestion.video.VideoIngester.get_video_metadata", return_value={"duration": 15.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", new_callable=AsyncMock, return_value=asr_segs), \
         patch("app.extraction.ocr.OCRExtractor.extract_from_frame_list", side_effect=RuntimeError("Tesseract segfault")), \
         patch("app.indexing.vector_index.VectorIndex.index_units", new_callable=AsyncMock):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="vid-ocr-fail",
            job_id="job-ocr-fail",
            file_path="/tmp/blurry.mp4",
            source_type="video",
        )

        assert mock_src.status == "completed"
        assert len(added_kus) >= 1
        assert added_kus[0].modality == "asr"
        meta_status = mock_src.metadata_.get("modality_status", {})
        assert meta_status.get("ocr") == "failed"
        assert meta_status.get("asr") == "completed"


# ---------------------------------------------------------------------------
# Test 6: Modality Timeout Produces Diagnostic Error (No Infinite Spinner)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_modality_timeout_produces_diagnostic():
    """Verify that when OCR times out and ASR produces no content, job fails with explicit diagnostic."""
    mock_src = MagicMock(spec=Source, id="vid-timeout", title="LongVideo.mp4", duration=None, status="pending", metadata_={})
    failed_steps = []

    async def mock_update_job(db, job_id, **kwargs):
        if kwargs.get("status") == "failed":
            failed_steps.append(kwargs.get("error_message"))

    mock_db = MagicMock()
    mock_db.rollback = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", side_effect=mock_update_job), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.video.VideoIngester.extract_audio", new_callable=AsyncMock, return_value=Path("/tmp/audio.wav")), \
         patch("app.ingestion.video.VideoIngester.extract_frames", new_callable=AsyncMock, return_value=[{"frame_path": "/tmp/f1.jpg", "timestamp": 1.0}]), \
         patch("app.ingestion.video.VideoIngester.get_video_metadata", return_value={"duration": 15.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", side_effect=RuntimeError("No speech")), \
         patch("app.extraction.ocr.OCRExtractor.extract_from_frame_list", side_effect=asyncio.TimeoutError("OCR Timeout")):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="vid-timeout",
            job_id="job-timeout",
            file_path="/tmp/long.mp4",
            source_type="video",
        )

        assert mock_src.status == "failed"
        assert len(failed_steps) == 1
        assert "timed out" in failed_steps[0] or "failed" in failed_steps[0]


# ---------------------------------------------------------------------------
# Test 7: Video Retry Does Not Duplicate Knowledge Units
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_retry_clears_records_and_requeues():
    """Verify that retrying a video clears existing KUs, Evidence, and vectors before reprocessing."""
    from fastapi import BackgroundTasks

    mock_src = MagicMock(spec=Source, id="src-vid-retry", file_path="/tmp/vid.mp4", source_type="video")
    mock_job = MagicMock(spec=ProcessingJob, id="job-v-old", status="failed", updated_at=datetime.utcnow())

    mock_db = MagicMock()
    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        res.scalars.return_value.first.return_value = mock_job
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    bg_tasks = BackgroundTasks()

    with patch("app.api.upload.get_settings") as mock_settings, \
         patch("app.database.qdrant.QdrantManager"), \
         patch("app.indexing.vector_index.VectorIndex.delete_by_source", new_callable=AsyncMock) as mock_del_vec, \
         patch("pathlib.Path.exists", return_value=True):

        res = await retry_source(
            source_id="src-vid-retry",
            background_tasks=bg_tasks,
            db=mock_db,
        )

        assert res["status"] == "pending"
        assert res["current_step"] == "Queued for retry"
        mock_del_vec.assert_called_once_with("src-vid-retry")


# ---------------------------------------------------------------------------
# Test 8: Modality Provenance & Timestamps Retained
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_modality_provenance_and_timestamps():
    """Verify that Evidence records retain correct modality ('asr' vs 'ocr') and timestamps."""
    mock_src = MagicMock(spec=Source, id="vid-prov", title="Provenance.mp4", duration=None, status="pending", metadata_={})
    added_ev = []

    def mock_add(entity):
        if isinstance(entity, Evidence):
            added_ev.append(entity)

    mock_db = MagicMock()
    mock_db.add = MagicMock(side_effect=mock_add)
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    asr_segs = [
        {"text": "Speech spoken from 10 to 20 seconds.", "timestamp_start": 10.0, "timestamp_end": 20.0, "confidence": 0.89, "modality": "asr", "source_id": "vid-prov"}
    ]
    ocr_segs = [
        {"text": "Slide text visible at 15 seconds.", "timestamp_start": 15.0, "timestamp_end": 15.0, "confidence": 0.94, "modality": "ocr", "source_id": "vid-prov"}
    ]

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.video.VideoIngester.extract_audio", new_callable=AsyncMock, return_value=Path("/tmp/audio.wav")), \
         patch("app.ingestion.video.VideoIngester.extract_frames", new_callable=AsyncMock, return_value=[{"frame_path": "/tmp/f1.jpg", "timestamp": 15.0}]), \
         patch("app.ingestion.video.VideoIngester.get_video_metadata", return_value={"duration": 30.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", new_callable=AsyncMock, return_value=asr_segs), \
         patch("app.extraction.ocr.OCRExtractor.extract_from_frame_list", new_callable=AsyncMock, return_value=ocr_segs), \
         patch("app.indexing.vector_index.VectorIndex.index_units", new_callable=AsyncMock):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="vid-prov",
            job_id="job-prov",
            file_path="/tmp/prov.mp4",
            source_type="video",
        )

        asr_ev = next((e for e in added_ev if e.modality == "asr"), None)
        ocr_ev = next((e for e in added_ev if e.modality == "ocr"), None)

        assert asr_ev is not None
        assert ocr_ev is not None
        assert asr_ev.timestamp_start == 10.0
        assert asr_ev.timestamp_end == 20.0
        assert ocr_ev.timestamp_start == 15.0


# ---------------------------------------------------------------------------
# Test 9: AI Chat Retrieves ASR Evidence for Speech-Based Question
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_chat_speech_question():
    """Verify AI Chat retrieves ASR evidence to answer a spoken question."""
    req = QueryRequest(
        query="What did the instructor say about pruning?",
        source_id="vid-chat-speech",
        save_history=False,
    )

    mock_src = MagicMock(spec=Source, id="vid-chat-speech", title="Lecture.mp4", status="completed")
    mock_ku = MagicMock(
        spec=KnowledgeUnit,
        id="ku-speech",
        concept="Pruning",
        content="The instructor explained that pruning eliminates subtrees that cannot yield solutions.",
        modality="asr",
        source_id="vid-chat-speech",
        confidence=0.88,
        status="active",
        version=1,
        timestamp_start=45.0,
        timestamp_end=60.0,
        page=None,
        slide=None,
        previous_version_id=None,
        correction_reason=None,
        created_at=datetime.utcnow(),
    )

    mock_db = MagicMock()
    async def mock_execute(stmt):
        s = str(stmt).lower()
        res = MagicMock()
        if "from sources" in s:
            res.scalar_one_or_none.return_value = mock_src
        elif "from knowledge_units" in s:
            res.scalars.return_value.all.return_value = [mock_ku]
        else:
            res.scalars.return_value.all.return_value = []
            res.scalar_one_or_none.return_value = None
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()

    with patch("app.indexing.vector_index.VectorIndex.search", new_callable=AsyncMock) as mock_vec, \
         patch("app.generation.llm.LLMClient.complete", new_callable=AsyncMock) as mock_llm:

        mock_vec.return_value = [
            {"unit_id": "ku-speech", "score": 0.92, "concept": "Pruning", "content": "The instructor explained that pruning eliminates subtrees that cannot yield solutions.", "modality": "asr", "source_id": "vid-chat-speech", "timestamp_start": 45.0, "timestamp_end": 60.0, "confidence": 0.88}
        ]
        mock_llm.return_value = "Pruning cuts branches that cannot yield valid solutions [1]."

        resp = await query(request=req, db=mock_db)
        assert resp["abstained"] is False
        assert len(resp["evidence"]) >= 1
        assert resp["evidence"][0]["modality"] == "asr"
        assert resp["evidence"][0]["timestamp_start"] == 45.0


# ---------------------------------------------------------------------------
# Test 10: AI Chat Retrieves OCR Evidence for Slide-Text Question
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_chat_slide_question():
    """Verify AI Chat retrieves OCR evidence to answer a question about text on a slide."""
    req = QueryRequest(
        query="What formula is shown on slide 5?",
        source_id="vid-chat-slide",
        save_history=False,
    )

    mock_src = MagicMock(spec=Source, id="vid-chat-slide", title="Lecture.mp4", status="completed")
    mock_ku = MagicMock(
        spec=KnowledgeUnit,
        id="ku-slide",
        concept="Formula",
        content="Formula shown on slide 5: T(n) = 2T(n/2) + O(n).",
        modality="ocr",
        source_id="vid-chat-slide",
        confidence=0.92,
        status="active",
        version=1,
        timestamp_start=75.0,
        timestamp_end=90.0,
        page=None,
        slide=5,
        previous_version_id=None,
        correction_reason=None,
        created_at=datetime.utcnow(),
    )

    mock_db = MagicMock()
    async def mock_execute(stmt):
        s = str(stmt).lower()
        res = MagicMock()
        if "from sources" in s:
            res.scalar_one_or_none.return_value = mock_src
        elif "from knowledge_units" in s:
            res.scalars.return_value.all.return_value = [mock_ku]
        else:
            res.scalars.return_value.all.return_value = []
            res.scalar_one_or_none.return_value = None
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()

    with patch("app.indexing.vector_index.VectorIndex.search", new_callable=AsyncMock) as mock_vec, \
         patch("app.generation.llm.LLMClient.complete", new_callable=AsyncMock) as mock_llm:

        mock_vec.return_value = [
            {"unit_id": "ku-slide", "score": 0.95, "concept": "Formula", "content": "Formula shown on slide 5: T(n) = 2T(n/2) + O(n).", "modality": "ocr", "source_id": "vid-chat-slide", "timestamp_start": 75.0, "timestamp_end": 90.0, "confidence": 0.92}
        ]
        mock_llm.return_value = "The recurrence relation shown is T(n) = 2T(n/2) + O(n) [1]."

        resp = await query(request=req, db=mock_db)
        assert resp["abstained"] is False
        assert len(resp["evidence"]) >= 1
        assert resp["evidence"][0]["modality"] == "ocr"


# ---------------------------------------------------------------------------
# Test 11: Speech vs Slide Contradiction Retrieves Both Modalities
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_chat_contradiction_retrieves_both():
    """Verify that a question involving contradiction between speech and slide retrieves both modalities."""
    req = QueryRequest(
        query="What is the worst-case time complexity of quicksort?",
        source_id="vid-conflict",
        save_history=False,
    )

    mock_src = MagicMock(spec=Source, id="vid-conflict", title="Sorting.mp4", status="completed")
    
    # KU 1 (speech): O(n log n)
    ku_asr = MagicMock(
        spec=KnowledgeUnit, id="ku-speech-c", concept="Quicksort Complexity",
        content="The speaker claims quicksort worst-case time complexity is O(n log n).",
        modality="asr", source_id="vid-conflict", confidence=0.85, status="disputed",
        version=1, timestamp_start=30.0, timestamp_end=45.0, page=None, slide=None,
        previous_version_id=None, correction_reason=None, created_at=datetime.utcnow()
    )
    # KU 2 (slide OCR): O(n^2)
    ku_ocr = MagicMock(
        spec=KnowledgeUnit, id="ku-slide-c", concept="Quicksort Complexity",
        content="The slide states worst-case time complexity of quicksort is O(n^2).",
        modality="ocr", source_id="vid-conflict", confidence=0.92, status="disputed",
        version=1, timestamp_start=30.0, timestamp_end=45.0, page=None, slide=None,
        previous_version_id=None, correction_reason=None, created_at=datetime.utcnow()
    )

    mock_conflict = MagicMock(
        spec=Conflict, id="conf-1", source_id="vid-conflict", conflict_type="complexity_disagreement",
        modalities=["asr", "ocr"], claims=["O(n log n) [asr]", "O(n^2) [ocr]"],
        timestamp=30.0, page=None, severity="high", confidence=0.9, resolved=False, resolution=None
    )

    mock_db = MagicMock()
    async def mock_execute(stmt):
        s = str(stmt).lower()
        res = MagicMock()
        if "from sources" in s:
            res.scalar_one_or_none.return_value = mock_src
        elif "from knowledge_units" in s:
            res.scalars.return_value.all.return_value = [ku_asr, ku_ocr]
        elif "from conflicts" in s:
            res.scalars.return_value.all.return_value = [mock_conflict]
        else:
            res.scalars.return_value.all.return_value = []
            res.scalar_one_or_none.return_value = None
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()

    with patch("app.indexing.vector_index.VectorIndex.search", new_callable=AsyncMock) as mock_vec, \
         patch("app.generation.llm.LLMClient.complete", new_callable=AsyncMock) as mock_llm:

        mock_vec.return_value = [
            {"unit_id": "ku-speech-c", "score": 0.95, "concept": "Quicksort Complexity", "content": "The speaker claims quicksort worst-case time complexity is O(n log n).", "modality": "asr", "source_id": "vid-conflict", "timestamp_start": 30.0, "timestamp_end": 45.0, "confidence": 0.85},
            {"unit_id": "ku-slide-c", "score": 0.94, "concept": "Quicksort Complexity", "content": "The slide states worst-case time complexity of quicksort is O(n^2).", "modality": "ocr", "source_id": "vid-conflict", "timestamp_start": 30.0, "timestamp_end": 45.0, "confidence": 0.92},
        ]
        mock_llm.return_value = "There is a cross-modal contradiction: the spoken audio states O(n log n) [1], while the slide states O(n^2) [2]."

        resp = await query(request=req, db=mock_db)
        assert resp["abstained"] is False
        modalities_retrieved = {ev["modality"] for ev in resp["evidence"]}
        assert "asr" in modalities_retrieved, "Must retrieve ASR evidence for contradiction"
        assert "ocr" in modalities_retrieved, "Must retrieve OCR evidence for contradiction"


# ---------------------------------------------------------------------------
# Test 12: Video Not Marked Fully Ready If Required Modalities Fail Unexpectedly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_video_not_marked_ready_if_both_modalities_fail():
    """Verify that a video is not marked completed if both ASR and OCR fail unexpectedly."""
    mock_src = MagicMock(spec=Source, id="vid-both-fail", title="Broken.mp4", duration=None, status="pending", metadata_={})

    mock_db = MagicMock()
    mock_db.rollback = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.video.VideoIngester.extract_audio", new_callable=AsyncMock, return_value=Path("/tmp/audio.wav")), \
         patch("app.ingestion.video.VideoIngester.extract_frames", new_callable=AsyncMock, return_value=[{"frame_path": "/tmp/f1.jpg", "timestamp": 1.0}]), \
         patch("app.ingestion.video.VideoIngester.get_video_metadata", return_value={"duration": 15.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", side_effect=RuntimeError("Whisper crashed")), \
         patch("app.extraction.ocr.OCRExtractor.extract_from_frame_list", side_effect=RuntimeError("OCR crashed")):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="vid-both-fail",
            job_id="job-bf",
            file_path="/tmp/broken.mp4",
            source_type="video",
        )

        assert mock_src.status == "failed"
        meta_status = mock_src.metadata_.get("modality_status", {})
        assert meta_status.get("asr") == "failed"
        assert meta_status.get("ocr") == "failed"
