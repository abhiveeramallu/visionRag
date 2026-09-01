"""
Upload and ingestion endpoints for VisionRAG-X.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database.postgres import get_db
from app.knowledge.models import Source, ProcessingJob
from app.schemas.requests import YouTubeIngestRequest
from app.schemas.responses import JobStatus, JobStatusResponse, SourceResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    '.mp4': 'video', '.mkv': 'video',
    '.mp3': 'audio', '.wav': 'audio',
    '.pdf': 'pdf',
    '.ppt': 'ppt', '.pptx': 'ppt',
    '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image', '.webp': 'image',
}


def _detect_source_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ALLOWED_EXTENSIONS.get(ext, 'unknown')


async def _update_job(db: AsyncSession, job_id: str, **kwargs) -> None:
    """Update a ProcessingJob record in the database."""
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.updated_at = datetime.utcnow()
        await db.commit()


# ---------------------------------------------------------------------------
# Background ingestion pipeline
# ---------------------------------------------------------------------------

async def run_ingestion_pipeline(
    source_id: str,
    job_id: str,
    file_path: Optional[str],
    source_type: str,
    youtube_url: Optional[str] = None,
) -> None:
    """
    Background task: full ingestion pipeline for a source.

    Steps:
    1. Download (YouTube) or load (file)
    2. Extract audio / frames
    3. ASR transcription
    4. OCR on frames/pages
    5. Timestamp alignment
    6. Knowledge unit creation
    7. Embedding + Qdrant indexing
    8. Update job to completed
    """
    from app.database.postgres import async_session as AsyncSessionLocal

    settings = get_settings()

    async with AsyncSessionLocal() as db:
        try:
            logger.info('Starting ingestion pipeline for source %s (type=%s)', source_id, source_type)
            # --- Step 1: Download / prepare ---
            await _update_job(db, job_id, status='processing', current_step='Downloading', progress=0.05)

            if source_type == 'youtube' and youtube_url:
                from app.ingestion.youtube import YouTubeIngester
                ingester = YouTubeIngester()
                output_dir = Path(settings.upload_dir) / source_id
                output_dir.mkdir(parents=True, exist_ok=True)
                dl = await ingester.download(youtube_url, output_dir)
                file_path = dl.get('file_path') or dl.get('audio_path')
                # Update source metadata
                result = await db.execute(select(Source).where(Source.id == source_id))
                src = result.scalar_one_or_none()
                if src and dl.get('metadata'):
                    meta = dl['metadata']
                    src.title = meta.get('title', src.title)
                    src.duration = meta.get('duration')
                    src.channel = meta.get('channel')
                    src.upload_date = meta.get('upload_date')
                    await db.commit()
                source_type = 'video' if file_path and Path(file_path).suffix in ('.mp4', '.mkv', '.webm') else 'audio'

            if not file_path or not Path(file_path).exists():
                raise FileNotFoundError(f'Source file not found: {file_path}')

            # --- Step 2: Extract audio + frames (video only) ---
            audio_path = None
            frames = []
            total_duration = 0.0

            if source_type in ('video', 'youtube'):
                await _update_job(db, job_id, current_step='Extracting audio and frames', progress=0.15)
                from app.ingestion.video import VideoIngester
                vi = VideoIngester()
                frames_dir = Path(settings.frames_dir) / source_id
                frames_dir.mkdir(parents=True, exist_ok=True)
                audio_path = await vi.extract_audio(Path(file_path), frames_dir)
                frames = await vi.extract_frames(Path(file_path), frames_dir)
                meta = vi.get_video_metadata(Path(file_path))
                total_duration = meta.get('duration', 0.0)
            elif source_type == 'audio':
                await _update_job(db, job_id, current_step='Preparing audio', progress=0.15)
                from app.ingestion.audio import AudioIngester
                ai = AudioIngester()
                audio_out = Path(settings.processed_dir) / source_id
                audio_out.mkdir(parents=True, exist_ok=True)
                audio_path = await ai.prepare_audio(Path(file_path), audio_out)
                meta = ai.get_audio_metadata(audio_path)
                total_duration = meta.get('duration', 0.0)

            # --- Step 3: ASR ---
            asr_segments = []
            av_formula_segments = []
            av_code_segments = []
            if audio_path and source_type in ('video', 'audio', 'youtube'):
                await _update_job(db, job_id, current_step='Transcribing audio (ASR)', progress=0.30)
                try:
                    from app.extraction.asr import ASRExtractor
                    from app.extraction.formula import FormulaExtractor
                    from app.extraction.code_parser import CodeParser
                    asr = ASRExtractor(settings)
                    asr_segments = await asr.transcribe(audio_path, source_id)

                    formula_extractor = FormulaExtractor()
                    code_parser = CodeParser()
                    for seg in asr_segments:
                        seg_text = seg.get('text', '')
                        for match in formula_extractor.extract_from_text(seg_text):
                            av_formula_segments.append({
                                'text': match, 'confidence': 0.7, 'modality': 'formula',
                                'source_id': source_id,
                                'timestamp_start': seg.get('timestamp_start') or seg.get('start'),
                                'timestamp_end': seg.get('timestamp_end') or seg.get('end'),
                            })
                        for block in code_parser.extract_code_blocks(seg_text):
                            av_code_segments.append({
                                'text': block['code'], 'confidence': block['confidence'],
                                'modality': 'code', 'source_id': source_id,
                                'timestamp_start': seg.get('timestamp_start') or seg.get('start'),
                                'timestamp_end': seg.get('timestamp_end') or seg.get('end'),
                                'language': block['language'],
                            })
                except Exception as e:
                    logger.warning('ASR failed (not fatal): %s', e)

            # --- Step 4: OCR ---
            ocr_segments = []
            if frames or source_type in ('pdf', 'ppt', 'image'):
                await _update_job(db, job_id, current_step='Running OCR', progress=0.50)
                try:
                    from app.extraction.ocr import OCRExtractor
                    ocr_extractor = OCRExtractor(settings)
                    if frames:
                        ocr_segments = await ocr_extractor.extract_from_frame_list(frames, source_id)
                    elif source_type in ('pdf', 'ppt', 'image'):
                        pass
                except Exception as e:
                    logger.warning('OCR failed (not fatal): %s', e)

            # Handle PDF/PPT/Image text extraction
            formula_segments = []
            code_segments = []
            if source_type == 'pdf':
                await _update_job(db, job_id, current_step='Extracting PDF text', progress=0.45)
                from app.ingestion.pdf import PDFIngester
                from app.extraction.formula import FormulaExtractor
                from app.extraction.code_parser import CodeParser
                pdf_ingester = PDFIngester()
                formula_extractor = FormulaExtractor()
                code_parser = CodeParser()
                out_dir = Path(settings.processed_dir) / source_id
                out_dir.mkdir(parents=True, exist_ok=True)
                pages = await pdf_ingester.extract(Path(file_path), out_dir)

                has_page_images = any(page['images'] for page in pages)
                ocr_extractor = None
                if has_page_images:
                    await _update_job(db, job_id, current_step='Running OCR', progress=0.50)
                    try:
                        from app.extraction.ocr import OCRExtractor
                        ocr_extractor = OCRExtractor(settings)
                    except Exception as e:
                        logger.warning('OCR extractor init failed (not fatal): %s', e)

                total_images = sum(len(page['images']) for page in pages)
                images_done = 0

                for page in pages:
                    page_num = page['page_num']
                    page_text = page['text']
                    asr_segments.append({
                        'text': page_text, 'start': None, 'end': None,
                        'confidence': 0.95, 'modality': 'text',
                        'source_id': source_id, 'page': page_num,
                        'timestamp_start': None, 'timestamp_end': None
                    })

                    for match in formula_extractor.extract_from_text(page_text):
                        formula_segments.append({
                            'text': match, 'confidence': 0.75, 'modality': 'formula',
                            'source_id': source_id, 'page': page_num,
                            'timestamp_start': None, 'timestamp_end': None,
                        })

                    for block in code_parser.extract_code_blocks(page_text):
                        code_segments.append({
                            'text': block['code'], 'confidence': block['confidence'],
                            'modality': 'code', 'source_id': source_id, 'page': page_num,
                            'timestamp_start': None, 'timestamp_end': None,
                            'language': block['language'],
                        })

                    if ocr_extractor and page['images']:
                        for img in page['images']:
                            try:
                                img_ocr = await ocr_extractor.extract_from_image(
                                    Path(img['image_path']), source_id, page=page_num
                                )
                                for seg in img_ocr:
                                    ocr_segments.append({
                                        'text': seg['text'], 'start': None, 'end': None,
                                        'confidence': seg.get('confidence', 0.85), 'modality': 'ocr',
                                        'source_id': source_id, 'page': page_num,
                                        'timestamp_start': None, 'timestamp_end': None,
                                    })
                            except Exception as e:
                                logger.warning('PDF page image OCR failed (not fatal): %s', e)
                            finally:
                                images_done += 1
                                if total_images:
                                    ocr_progress = 0.50 + 0.15 * (images_done / total_images)
                                    await _update_job(
                                        db, job_id,
                                        current_step=f'Running OCR ({images_done}/{total_images} images)',
                                        progress=ocr_progress,
                                    )
            elif source_type == 'ppt':
                await _update_job(db, job_id, current_step='Extracting PPT text', progress=0.45)
                from app.ingestion.ppt import PPTIngester
                from app.extraction.formula import FormulaExtractor
                from app.extraction.code_parser import CodeParser
                ppt_ingester = PPTIngester()
                formula_extractor = FormulaExtractor()
                code_parser = CodeParser()
                out_dir = Path(settings.processed_dir) / source_id
                out_dir.mkdir(parents=True, exist_ok=True)
                slides = await ppt_ingester.extract(Path(file_path), out_dir)

                has_slide_images = any(slide['images'] for slide in slides)
                ocr_extractor = None
                if has_slide_images:
                    await _update_job(db, job_id, current_step='Running OCR', progress=0.50)
                    try:
                        from app.extraction.ocr import OCRExtractor
                        ocr_extractor = OCRExtractor(settings)
                    except Exception as e:
                        logger.warning('OCR extractor init failed (not fatal): %s', e)

                total_slide_images = sum(len(slide['images']) for slide in slides)
                slide_images_done = 0

                for slide in slides:
                    slide_num = slide['slide_num']
                    slide_text = '\n\n'.join(t for t in (slide.get('title', ''), slide['text'], slide.get('notes', '')) if t)
                    asr_segments.append({
                        'text': slide_text, 'start': None, 'end': None,
                        'confidence': 0.95, 'modality': 'text',
                        'source_id': source_id, 'page': slide_num,
                        'timestamp_start': None, 'timestamp_end': None
                    })

                    for match in formula_extractor.extract_from_text(slide_text):
                        formula_segments.append({
                            'text': match, 'confidence': 0.75, 'modality': 'formula',
                            'source_id': source_id, 'page': slide_num,
                            'timestamp_start': None, 'timestamp_end': None,
                        })

                    for block in code_parser.extract_code_blocks(slide_text):
                        code_segments.append({
                            'text': block['code'], 'confidence': block['confidence'],
                            'modality': 'code', 'source_id': source_id, 'page': slide_num,
                            'timestamp_start': None, 'timestamp_end': None,
                            'language': block['language'],
                        })

                    if ocr_extractor and slide['images']:
                        for img in slide['images']:
                            try:
                                img_ocr = await ocr_extractor.extract_from_image(
                                    Path(img['image_path']), source_id, page=slide_num
                                )
                                for seg in img_ocr:
                                    ocr_segments.append({
                                        'text': seg['text'], 'start': None, 'end': None,
                                        'confidence': seg.get('confidence', 0.85), 'modality': 'ocr',
                                        'source_id': source_id, 'page': slide_num,
                                        'timestamp_start': None, 'timestamp_end': None,
                                    })
                            except Exception as e:
                                logger.warning('PPT slide image OCR failed (not fatal): %s', e)
                            finally:
                                slide_images_done += 1
                                if total_slide_images:
                                    ocr_progress = 0.50 + 0.15 * (slide_images_done / total_slide_images)
                                    await _update_job(
                                        db, job_id,
                                        current_step=f'Running OCR ({slide_images_done}/{total_slide_images} images)',
                                        progress=ocr_progress,
                                    )
            elif source_type == 'image':
                await _update_job(db, job_id, current_step='Running OCR on image', progress=0.45)
                try:
                    from app.extraction.ocr import OCRExtractor
                    from app.extraction.formula import FormulaExtractor
                    from app.extraction.code_parser import CodeParser
                    ocr_extractor = OCRExtractor(settings)
                    image_ocr = await ocr_extractor.extract_from_image(Path(file_path), source_id, page=1)
                    formula_extractor = FormulaExtractor()
                    code_parser = CodeParser()
                    for seg in image_ocr:
                        ocr_segments.append({
                            'text': seg['text'], 'start': None, 'end': None,
                            'confidence': seg.get('confidence', 0.9), 'modality': 'ocr',
                            'source_id': source_id, 'page': 1,
                            'timestamp_start': None, 'timestamp_end': None
                        })
                        for match in formula_extractor.extract_from_text(seg['text']):
                            formula_segments.append({
                                'text': match, 'confidence': 0.7, 'modality': 'formula',
                                'source_id': source_id, 'page': 1,
                                'timestamp_start': None, 'timestamp_end': None,
                            })
                        for block in code_parser.extract_code_blocks(seg['text']):
                            code_segments.append({
                                'text': block['code'], 'confidence': block['confidence'],
                                'modality': 'code', 'source_id': source_id, 'page': 1,
                                'timestamp_start': None, 'timestamp_end': None,
                                'language': block['language'],
                            })
                except Exception as e:
                    logger.warning('Image OCR failed: %s', e)

            # --- Step 5: Alignment ---
            await _update_job(db, job_id, current_step='Aligning modalities', progress=0.65)
            from app.alignment.timestamp_alignment import TimestampAligner
            aligner = TimestampAligner()
            if source_type in ('video', 'audio', 'youtube'):
                windows = aligner.align_video_segments(
                    source_id=source_id,
                    asr_segments=asr_segments,
                    ocr_segments=ocr_segments,
                    vision_segments=[],
                    formula_segments=av_formula_segments,
                    code_segments=av_code_segments,
                    total_duration=total_duration,
                )
            else:
                windows = aligner.align_document_segments(
                    source_id=source_id,
                    text_segments=asr_segments,
                    ocr_segments=ocr_segments,
                    total_pages=max((s.get('page', 1) or 1) for s in asr_segments) if asr_segments else 1,
                    doc_type=source_type,
                    formula_segments=formula_segments,
                    code_segments=code_segments,
                )

            # --- Step 6: Create knowledge units ---
            await _update_job(db, job_id, current_step='Creating knowledge units', progress=0.75)
            from app.verification.conflict_detector import ConflictDetector
            from app.verification.confidence import ConfidenceScorer
            from app.knowledge.evolution import detect_correction_phrase, content_keywords, keyword_overlap
            detector = ConflictDetector(settings)
            scorer = ConfidenceScorer()
            all_conflicts = detector.detect_all(windows)

            ku_dicts = []
            evidence_rows = []
            concept_registry = []  # ordered list of {'keywords', 'ku', 'concept'} seen so far, for correction linking
            for window in windows:
                all_segs = (
                    window.get('asr_segments', [])
                    + window.get('ocr_segments', [])
                    + window.get('formula_segments', [])
                    + window.get('code_segments', [])
                )
                combined_text = ' '.join(s.get('text', '') for s in all_segs).strip()
                if not combined_text:
                    continue

                # Derive concept from first sentence or first 60 chars
                first_sentence = combined_text.split('.')[0][:80].strip()
                concept = first_sentence if first_sentence else combined_text[:60]

                ku_id = str(uuid.uuid4())
                conf = scorer.score_segment(
                    all_segs[0] if all_segs else {'confidence': 0.5, 'modality': 'text', 'text': ''},
                    window,
                    all_conflicts,
                )
                primary_modality = (
                    window.get('code_segments')
                    or window.get('formula_segments')
                    or window.get('ocr_segments')
                    or window.get('asr_segments')
                    or [{}]
                )[0].get('modality', 'text')

                # --- Correction / version-chain detection (VKEG) ---
                # Only treat this as a correction of an earlier unit when BOTH
                # explicit correction language is present AND it topically
                # overlaps a recently-seen concept for this source — either
                # signal alone is too weak and would mislink unrelated content.
                previous_version_id = None
                ku_version = 1
                ku_status = 'active'
                correction_reason = None
                new_keywords = content_keywords(combined_text)

                correction_phrase = detect_correction_phrase(combined_text)
                if correction_phrase and concept_registry:
                    best_entry, best_overlap = None, 0.0
                    for entry in reversed(concept_registry):
                        overlap = keyword_overlap(new_keywords, entry['keywords'])
                        if overlap > best_overlap:
                            best_overlap, best_entry = overlap, entry
                    if best_entry and best_overlap >= 0.15:
                        previous_version_id = best_entry['ku'].id
                        ku_version = best_entry['ku'].version + 1
                        ku_status = 'verified'
                        correction_reason = (
                            f'Detected correction language ("{correction_phrase}") updating an '
                            f'earlier statement about "{best_entry["concept"][:60]}".'
                        )
                        best_entry['ku'].status = 'superseded'
                        concept = best_entry['concept']  # keep the concept name stable across versions

                ku = KnowledgeUnit(
                    id=ku_id,
                    concept=concept,
                    content=combined_text[:2000],
                    modality=primary_modality,
                    source_id=source_id,
                    timestamp_start=window.get('window_start'),
                    timestamp_end=window.get('window_end'),
                    page=window.get('page'),
                    slide=window.get('slide'),
                    confidence=conf,
                    status=ku_status,
                    version=ku_version,
                    previous_version_id=previous_version_id,
                    correction_reason=correction_reason,
                )
                db.add(ku)
                concept_registry.append({'keywords': new_keywords, 'ku': ku, 'concept': concept})

                ku_dicts.append({
                    'id': ku_id, 'concept': concept,
                    'content': combined_text[:2000],
                    'modality': primary_modality,
                    'source_id': source_id,
                    'timestamp_start': window.get('window_start'),
                    'timestamp_end': window.get('window_end'),
                    'page': window.get('page'),
                    'slide': window.get('slide'),
                    'confidence': conf,
                    'status': ku_status,
                    'version': ku_version,
                })

                # --- Evidence rows: one per raw segment supporting this unit ---
                for seg in all_segs:
                    evidence_rows.append(Evidence(
                        id=str(uuid.uuid4()),
                        knowledge_unit_id=ku_id,
                        text=(seg.get('text', '') or '')[:2000],
                        modality=seg.get('modality', primary_modality),
                        source_id=source_id,
                        timestamp_start=seg.get('timestamp_start') if seg.get('timestamp_start') is not None else seg.get('start'),
                        timestamp_end=seg.get('timestamp_end') if seg.get('timestamp_end') is not None else seg.get('end'),
                        page=window.get('page'),
                        extraction_confidence=seg.get('confidence', conf),
                    ))

            for ev in evidence_rows:
                db.add(ev)

            # Save conflicts to DB
            from app.knowledge.models import Conflict
            for c in all_conflicts:
                db.add(Conflict(
                    id=str(uuid.uuid4()),
                    source_id=source_id,
                    conflict_type=c.get('type', 'unknown'),
                    modalities=c.get('sources', []),
                    claims=c.get('claims', []),
                    timestamp=c.get('timestamp'),
                    page=c.get('page'),
                    severity=c.get('severity', 'low'),
                    confidence=c.get('confidence', 0.5),
                ))
            await db.commit()

            # --- Step 7: Index ---
            await _update_job(db, job_id, current_step='Indexing knowledge units', progress=0.88)
            try:
                from app.database.qdrant import QdrantManager
                from app.indexing.vector_index import VectorIndex
                qdrant = QdrantManager(settings)
                vi_index = VectorIndex(settings, qdrant)
                await vi_index.index_units(ku_dicts)
            except Exception as e:
                logger.warning('Vector indexing failed (not fatal): %s', e)

            # --- Step 8: Complete ---
            # Update source status
            result = await db.execute(select(Source).where(Source.id == source_id))
            src = result.scalar_one_or_none()
            if src:
                src.status = 'completed'
                await db.commit()

            await _update_job(
                db, job_id,
                status='completed',
                current_step='Done',
                progress=1.0,
            )
            logger.info('Ingestion complete for source %s', source_id)

        except Exception as e:
            logger.error('Ingestion failed for source %s: %s', source_id, e, exc_info=True)
            try:
                await _update_job(
                    db, job_id,
                    status='failed',
                    current_step='Failed',
                    error_message=str(e)[:500],
                )
                result = await db.execute(select(Source).where(Source.id == source_id))
                src = result.scalar_one_or_none()
                if src:
                    src.status = 'failed'
                    await db.commit()
            except Exception:
                pass


# Need KnowledgeUnit import inside the function to avoid circular imports
from app.knowledge.models import KnowledgeUnit, Evidence  # noqa: E402


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post('/api/upload', status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file (video, audio, PDF, PPT, image) for processing."""
    settings = get_settings()
    ext = Path(file.filename or '').suffix.lower()
    source_type = _detect_source_type(file.filename or '')
    if source_type == 'unknown':
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f'Unsupported file type: {ext}. Allowed: {list(ALLOWED_EXTENSIONS.keys())}',
        )

    source_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    # Save file
    upload_dir = Path(settings.upload_dir) / source_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / (file.filename or f'file{ext}')
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)

    # Create DB records
    source = Source(
        id=source_id,
        title=file.filename or 'Uploaded file',
        source_type=source_type,
        file_path=str(file_path),
        status='pending',
    )
    job = ProcessingJob(id=job_id, source_id=source_id, status='pending')
    db.add(source)
    db.add(job)
    await db.commit()

    background_tasks.add_task(
        run_ingestion_pipeline,
        source_id=source_id,
        job_id=job_id,
        file_path=str(file_path),
        source_type=source_type,
    )

    return {
        'job_id': job_id,
        'source_id': source_id,
        'status': 'pending',
        'progress': 0.0,
        'current_step': 'Queued',
        'error': None,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
    }


@router.post('/api/youtube', status_code=status.HTTP_202_ACCEPTED)
async def ingest_youtube(
    request: YouTubeIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Submit a YouTube URL for ingestion."""
    source_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    source = Source(
        id=source_id,
        title=request.title or 'YouTube Video',
        source_type='youtube',
        url=str(request.url),
        status='pending',
    )
    job = ProcessingJob(id=job_id, source_id=source_id, status='pending')
    db.add(source)
    db.add(job)
    await db.commit()

    background_tasks.add_task(
        run_ingestion_pipeline,
        source_id=source_id,
        job_id=job_id,
        file_path=None,
        source_type='youtube',
        youtube_url=str(request.url),
    )

    return {
        'job_id': job_id,
        'source_id': source_id,
        'status': 'pending',
        'progress': 0.0,
        'current_step': 'Queued',
        'error': None,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
    }


@router.get('/api/status/{source_id}')
async def get_status(source_id: str, db: AsyncSession = Depends(get_db)):
    """Get the processing job status for a source."""
    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.source_id == source_id)
        .order_by(ProcessingJob.created_at.desc())
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f'No processing job found for source {source_id}')

    return {
        'job_id': job.id,
        'source_id': job.source_id,
        'status': job.status,
        'progress': job.progress or 0.0,
        'current_step': job.current_step,
        'error': job.error_message,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'updated_at': job.updated_at.isoformat() if job.updated_at else None,
    }
