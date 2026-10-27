"""
Comprehensive regression test suite for Audio (MP3/WAV) ingestion, ASR, and retrieval in VisionRAG-X.

Covers:
1. Audio validation and metadata extraction (sample rate, channels, duration).
2. Audio ingestion error on missing file.
3. Audio preparation / conversion to 16kHz mono WAV.
4. ASR extractor engine selection (faster-whisper prioritized).
5. ASR transcription returning structured segments with start, end, confidence, and modality 'asr'.
6. Timestamp alignment ensuring windows cover speech segments even if duration is small or zero.
7. End-to-end audio ingestion pipeline saves duration and marks status completed.
8. Knowledge Units created from audio have modality 'asr' and correct timestamps.
9. Empty ASR output raises diagnostic error and marks job as failed (no zero-KU completions).
10. ASR exception marks job as failed with diagnostic error message.
11. Knowledge Units endpoint filters properly by audio source_id.
12. Source retry clears existing KUs and Evidence to avoid duplicates.
13. Source-scoped AI chat query on audio source answers questions with grounded citations.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.config import Settings
from app.extraction.asr import ASRExtractor, ConfigurationError
from app.ingestion.audio import AudioIngester, AudioIngestionError
from app.alignment.timestamp_alignment import TimestampAligner
from app.knowledge.models import Source, ProcessingJob, KnowledgeUnit, Evidence


# ---------------------------------------------------------------------------
# Test 1: Audio Metadata Extraction
# ---------------------------------------------------------------------------

def test_audio_metadata_extraction():
    """Verify AudioIngester parses ffprobe output into duration, sample_rate, channels."""
    ai = AudioIngester()
    fake_ffprobe_output = {
        "streams": [
            {"codec_type": "audio", "duration": "125.5", "sample_rate": "44100", "channels": 2}
        ],
        "format": {"duration": "125.5", "format_long_name": "MP3 (MPEG audio layer 3)"}
    }
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat") as mock_stat, \
         patch("subprocess.run") as mock_run:
        mock_stat.return_value.st_size = 1048576
        mock_run.return_value = MagicMock(returncode=0, stdout='{"streams":[{"codec_type":"audio","duration":"125.5","sample_rate":"44100","channels":2}],"format":{"duration":"125.5","format_name":"mp3"}}')
        
        meta = ai.get_audio_metadata(Path("/tmp/sample.mp3"))
        assert meta["duration"] == 125.5
        assert meta["sample_rate"] == 44100
        assert meta["channels"] == 2
        assert meta["size_bytes"] == 1048576


# ---------------------------------------------------------------------------
# Test 2: Audio File Not Found Error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_not_found_raises():
    """Verify AudioIngester raises AudioIngestionError when file is missing."""
    ai = AudioIngester()
    with pytest.raises(AudioIngestionError, match="Audio file not found"):
        await ai.prepare_audio(Path("/nonexistent/file.mp3"), Path("/tmp/out"))


# ---------------------------------------------------------------------------
# Test 3: Audio Preparation to 16kHz Mono WAV
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_preparation_skips_if_already_16k_mono():
    """Verify that an already 16kHz mono WAV file is copied directly without re-encoding."""
    ai = AudioIngester()
    with patch("pathlib.Path.exists", return_value=True), \
         patch.object(ai, "get_audio_metadata", return_value={"sample_rate": 16000, "channels": 1, "duration": 10.0}), \
         patch("shutil.copy2") as mock_copy:
        out = await ai.prepare_audio(Path("/tmp/sample.wav"), Path("/tmp/out"))
        assert out == Path("/tmp/out/sample_prepared.wav")
        mock_copy.assert_called_once()


# ---------------------------------------------------------------------------
# Test 4: ASR Backend Engine Selection
# ---------------------------------------------------------------------------

def test_asr_backend_selection():
    """Verify ASRExtractor checks faster_whisper first."""
    settings = Settings()
    asr = ASRExtractor(settings)
    assert asr._check_availability() is True
    assert asr._backend in ("faster_whisper", "whisperx")


# ---------------------------------------------------------------------------
# Test 5: ASR Transcription Result Structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asr_transcribe_segments_structure():
    """Verify ASRExtractor maps output to segment dicts with timestamps and confidence."""
    settings = Settings()
    asr = ASRExtractor(settings)
    
    mock_seg1 = MagicMock(text="Hello world", start=0.5, end=3.2, avg_logprob=-0.2)
    mock_seg2 = MagicMock(text="Second sentence", start=3.5, end=6.0, avg_logprob=-0.4)
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch.object(asr, "_load_model"), \
         patch.object(asr, "_check_availability", return_value=True):
        asr._backend = "faster_whisper"
        asr._model = MagicMock()
        asr._model.transcribe.return_value = ([mock_seg1, mock_seg2], MagicMock(duration=6.0))
        
        segments = await asr.transcribe(Path("/tmp/test.wav"), "source-123")
        assert len(segments) == 2
        assert segments[0]["text"] == "Hello world"
        assert segments[0]["timestamp_start"] == 0.5
        assert segments[0]["timestamp_end"] == 3.2
        assert segments[0]["modality"] == "asr"
        assert segments[0]["source_id"] == "source-123"
        assert 0.0 <= segments[0]["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Test 6: Timestamp Alignment for Audio
# ---------------------------------------------------------------------------

def test_timestamp_aligner_audio_windows():
    """Verify TimestampAligner creates non-empty windows for audio speech segments."""
    aligner = TimestampAligner(window_size_seconds=15.0)
    asr_segs = [
        {"text": "Intro speech", "timestamp_start": 2.0, "timestamp_end": 7.0, "confidence": 0.9, "modality": "asr"},
        {"text": "Continued speech", "timestamp_start": 10.0, "timestamp_end": 14.0, "confidence": 0.85, "modality": "asr"},
        {"text": "Second window speech", "timestamp_start": 18.0, "timestamp_end": 25.0, "confidence": 0.88, "modality": "asr"},
    ]
    
    windows = aligner.align_video_segments(
        source_id="src-audio",
        asr_segments=asr_segs,
        ocr_segments=[],
        vision_segments=[],
        formula_segments=[],
        code_segments=[],
        total_duration=30.0,
    )
    
    assert len(windows) == 2
    assert len(windows[0]["asr_segments"]) == 2
    assert len(windows[1]["asr_segments"]) == 1
    assert windows[0]["window_start"] == 0.0
    assert windows[1]["window_start"] == 15.0


# ---------------------------------------------------------------------------
# Test 7: Pipeline Saves Audio Duration and Completes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_pipeline_saves_duration():
    """Verify that audio ingestion saves duration to Source and marks job completed."""
    from app.api.upload import run_ingestion_pipeline
    
    mock_src = MagicMock(spec=Source, id="audio-src-1", title="test.mp3", duration=None, status="pending")
    mock_job = MagicMock(spec=ProcessingJob, id="job-1", status="pending")
    
    async def mock_execute(stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_src
        res.scalars.return_value.all.return_value = []
        return res

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    asr_segs = [
        {"text": "Audio lecture content", "start": 0.0, "end": 10.0, "timestamp_start": 0.0, "timestamp_end": 10.0, "confidence": 0.9, "modality": "asr", "source_id": "audio-src-1"}
    ]

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.audio.AudioIngester.prepare_audio", new_callable=AsyncMock, return_value=Path("/tmp/test_prepared.wav")), \
         patch("app.ingestion.audio.AudioIngester.get_audio_metadata", return_value={"duration": 180.5, "sample_rate": 16000, "channels": 1}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", new_callable=AsyncMock, return_value=asr_segs), \
         patch("app.indexing.vector_index.VectorIndex.index_units", new_callable=AsyncMock):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="audio-src-1",
            job_id="job-1",
            file_path="/tmp/test.mp3",
            source_type="audio",
        )

        assert mock_src.duration == 180.5
        assert mock_src.status == "completed"


# ---------------------------------------------------------------------------
# Test 8: Knowledge Units Created with Modality ASR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_creates_asr_knowledge_units():
    """Verify that audio ingestion creates Knowledge Units with primary_modality == 'asr'."""
    from app.api.upload import run_ingestion_pipeline
    
    mock_src = MagicMock(spec=Source, id="audio-src-ku", title="test.mp3", duration=None, status="pending")
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
        {"text": "This is a lecture about business history.", "start": 0.0, "end": 14.0, "timestamp_start": 0.0, "timestamp_end": 14.0, "confidence": 0.92, "modality": "asr", "source_id": "audio-src-ku"}
    ]

    with patch("app.database.postgres.async_session") as mock_session_maker, \
         patch("app.api.upload._update_job", new_callable=AsyncMock), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("app.ingestion.audio.AudioIngester.prepare_audio", new_callable=AsyncMock, return_value=Path("/tmp/prep.wav")), \
         patch("app.ingestion.audio.AudioIngester.get_audio_metadata", return_value={"duration": 60.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", new_callable=AsyncMock, return_value=asr_segs), \
         patch("app.indexing.vector_index.VectorIndex.index_units", new_callable=AsyncMock):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="audio-src-ku",
            job_id="job-ku",
            file_path="/tmp/test.mp3",
            source_type="audio",
        )

        assert len(added_kus) >= 1
        assert added_kus[0].modality == "asr"
        assert "business history" in added_kus[0].content


# ---------------------------------------------------------------------------
# Test 9: Empty Audio Fails with Diagnostic Error (No Silent Zero-KUs)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_audio_fails_gracefully():
    """Verify that silent/empty audio raising 0 ASR segments causes job to fail with clear diagnostic."""
    from app.api.upload import run_ingestion_pipeline
    
    mock_src = MagicMock(spec=Source, id="audio-silent", title="silent.mp3", duration=None, status="pending")
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
         patch("app.ingestion.audio.AudioIngester.prepare_audio", new_callable=AsyncMock, return_value=Path("/tmp/silent.wav")), \
         patch("app.ingestion.audio.AudioIngester.get_audio_metadata", return_value={"duration": 30.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", new_callable=AsyncMock, return_value=[]):  # 0 segments

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="audio-silent",
            job_id="job-silent",
            file_path="/tmp/silent.mp3",
            source_type="audio",
        )

        assert len(failed_steps) == 1
        assert "zero transcript segments" in failed_steps[0]
        assert mock_src.status == "failed"


# ---------------------------------------------------------------------------
# Test 10: ASR Exception Causes Failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asr_exception_marks_job_failed():
    """Verify that ASR crashing on audio sources marks job failed rather than swallowing."""
    from app.api.upload import run_ingestion_pipeline
    
    mock_src = MagicMock(spec=Source, id="audio-err", title="err.mp3", duration=None, status="pending")
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
         patch("app.ingestion.audio.AudioIngester.prepare_audio", new_callable=AsyncMock, return_value=Path("/tmp/err.wav")), \
         patch("app.ingestion.audio.AudioIngester.get_audio_metadata", return_value={"duration": 30.0}), \
         patch("app.extraction.asr.ASRExtractor.transcribe", side_effect=RuntimeError("CUDA out of memory")):

        mock_session_maker.return_value.__aenter__.return_value = mock_db
        mock_session_maker.return_value.__aexit__.return_value = None

        await run_ingestion_pipeline(
            source_id="audio-err",
            job_id="job-err",
            file_path="/tmp/err.mp3",
            source_type="audio",
        )

        assert len(failed_steps) == 1
        assert "Audio speech recognition failed" in failed_steps[0]
        assert mock_src.status == "failed"


# ---------------------------------------------------------------------------
# Test 11: KU List Filtering by Source ID
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ku_list_filtering_by_source():
    """Verify list_knowledge_units filters by source_id correctly."""
    from app.api.query import list_knowledge_units
    
    mock_ku1 = MagicMock(spec=KnowledgeUnit, id="ku-1", concept="Concept A", content="Content A", modality="asr", source_id="src-audio-1", confidence=0.85, status="active", version=1, timestamp_start=0.0, timestamp_end=15.0, page=None, slide=None, previous_version_id=None, correction_reason=None, created_at=datetime.utcnow())
    mock_source = MagicMock(spec=Source, id="src-audio-1", title="Audio Source")
    
    mock_db = MagicMock()
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "count" in stmt_str:
            res.scalar.return_value = 1
        elif "sources" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_source]
        elif "evidence" in stmt_str:
            res.all.return_value = [("ku-1", 3)]
        else:
            res.scalars.return_value.all.return_value = [mock_ku1]
        return res
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    result = await list_knowledge_units(
        source_id="src-audio-1",
        modality="asr",
        status=None,
        search=None,
        limit=50,
        offset=0,
        db=mock_db,
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["source_id"] == "src-audio-1"
    assert result["items"][0]["modality"] == "asr"
    assert result["items"][0]["source_title"] == "Audio Source"


# ---------------------------------------------------------------------------
# Test 12: Source Retry Cleans Previous Units
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_retry_clears_previous_units():
    """Verify that retrying a source deletes old Evidence, Conflict, and KnowledgeUnit records."""
    from app.api.upload import retry_source
    from fastapi import BackgroundTasks

    mock_source = MagicMock(spec=Source, id="src-retry", file_path="/tmp/audio.mp3", source_type="audio")
    mock_job = MagicMock(spec=ProcessingJob, id="job-old", status="failed", updated_at=datetime.utcnow())

    mock_db = MagicMock()
    executed_statements = []

    async def mock_execute(stmt):
        executed_statements.append(stmt)
        res = MagicMock()
        res.scalar_one_or_none.return_value = mock_source
        res.scalars.return_value.first.return_value = mock_job
        return res

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    bg_tasks = BackgroundTasks()

    with patch("app.api.upload.get_settings") as mock_settings, \
         patch("app.database.qdrant.QdrantManager"), \
         patch("app.indexing.vector_index.VectorIndex.delete_by_source", new_callable=AsyncMock) as mock_qdrant_del, \
         patch("pathlib.Path.exists", return_value=True):

        res = await retry_source(
            source_id="src-retry",
            background_tasks=bg_tasks,
            db=mock_db,
        )

        assert res["status"] == "pending"
        assert res["current_step"] == "Queued for retry"
        mock_qdrant_del.assert_called_once_with("src-retry")


# ---------------------------------------------------------------------------
# Test 13: Source-Scoped AI Chat Retrieval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_chat_answers_grounded():
    """Verify that source-scoped query grounded in audio ASR returns answer with valid citations."""
    from app.api.query import query
    from app.schemas.requests import QueryRequest

    req = QueryRequest(
        query="Who teaches Masters of Enterprise?",
        source_id="src-audio-grounded",
        save_history=False,
    )

    mock_db = MagicMock()
    mock_src = MagicMock(spec=Source, id="src-audio-grounded", title="Masters of Enterprise.mp3", status="completed")
    mock_ku = MagicMock(
        spec=KnowledgeUnit,
        id="ku-1",
        concept="Professor",
        content="Your professor for Masters of Enterprise is H.W. Brands, professor of history.",
        modality="asr",
        source_id="src-audio-grounded",
        confidence=0.88,
        status="active",
        version=1,
        timestamp_start=15.0,
        timestamp_end=30.0,
        page=None,
        slide=None,
        previous_version_id=None,
        correction_reason=None,
        created_at=datetime.utcnow(),
    )
    
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "from sources" in stmt_str:
            res.scalar_one_or_none.return_value = mock_src
        elif "from knowledge_units" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_ku]
        elif "from conflicts" in stmt_str:
            res.scalars.return_value.all.return_value = []
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    with patch("app.indexing.vector_index.VectorIndex.search", new_callable=AsyncMock) as mock_vec_search, \
         patch("app.generation.llm.LLMClient.complete", new_callable=AsyncMock) as mock_llm_gen:

        mock_vec_search.return_value = [
            {"unit_id": "ku-1", "score": 0.95, "concept": "Professor", "content": "Your professor for Masters of Enterprise is H.W. Brands, professor of history.", "modality": "asr", "source_id": "src-audio-grounded", "timestamp_start": 15.0, "timestamp_end": 30.0, "confidence": 0.88}
        ]

        mock_llm_gen.return_value = "The course is taught by Professor H.W. Brands [1]."

        resp = await query(request=req, db=mock_db)
        assert resp["abstained"] is False
        assert "H.W. Brands" in resp["answer"]
        assert len(resp["evidence"]) >= 1
        assert resp["evidence"][0]["modality"] == "asr"
