"""
Summary, quiz, flashcard, and notes endpoints for VisionRAG-X.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database.postgres import get_db
from app.knowledge.models import KnowledgeUnit, Source
from app.schemas.requests import SummaryRequest, QuizRequest, FlashcardRequest, NotesRequest

router = APIRouter()
logger = logging.getLogger(__name__)


async def _load_units(source_id: str, db: AsyncSession):
    result = await db.execute(
        select(KnowledgeUnit)
        .where(KnowledgeUnit.source_id == source_id)
        .where(KnowledgeUnit.status != 'superseded')
        .limit(500)
    )
    return [
        {
            'id': u.id, 'concept': u.concept, 'content': u.content,
            'modality': u.modality, 'source_id': u.source_id,
            'timestamp_start': u.timestamp_start, 'timestamp_end': u.timestamp_end,
            'page': u.page, 'slide': u.slide, 'confidence': u.confidence,
            'status': u.status, 'version': u.version,
        }
        for u in result.scalars().all()
    ]


async def _get_source_or_404(source_id: str, db: AsyncSession):
    r = await db.execute(select(Source).where(Source.id == source_id))
    src = r.scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f'Source {source_id} not found')
    return src


@router.post('/api/summary')
async def generate_summary(request: SummaryRequest, db: AsyncSession = Depends(get_db)):
    """Generate a summary (overall / topic / timestamped) for a source."""
    settings = get_settings()
    source = await _get_source_or_404(request.source_id, db)
    units = await _load_units(request.source_id, db)

    if not units:
        raise HTTPException(status_code=422, detail='No knowledge units found. Has processing completed?')

    from app.generation.llm import LLMClient
    from app.generation.summary import SummaryGenerator
    llm = LLMClient(settings)
    gen = SummaryGenerator(llm)

    summary_type = request.summary_type.value if hasattr(request.summary_type, 'value') else str(request.summary_type)

    if summary_type == 'overall':
        result = await gen.generate_overall(units, source.title)
    elif summary_type == 'topic':
        if not request.topic:
            raise HTTPException(status_code=422, detail='topic field is required for topic summary')
        result = await gen.generate_topic(units, request.topic, source.title)
    elif summary_type == 'timestamped':
        result = await gen.generate_overall(units, source.title)  # simplified
    else:
        result = await gen.generate_overall(units, source.title)

    result['source_id'] = request.source_id
    return result


@router.post('/api/quiz')
async def generate_quiz(request: QuizRequest, db: AsyncSession = Depends(get_db)):
    """Generate quiz questions from a source's knowledge units."""
    settings = get_settings()
    source = await _get_source_or_404(request.source_id, db)
    units = await _load_units(request.source_id, db)

    if not units:
        raise HTTPException(status_code=422, detail='No knowledge units found. Has processing completed?')

    from app.generation.llm import LLMClient
    from app.generation.summary import QuizGenerator
    llm = LLMClient(settings)
    gen = QuizGenerator(llm)

    quiz_type = request.quiz_type.value if hasattr(request.quiz_type, 'value') else str(request.quiz_type)
    difficulty = request.difficulty.value if hasattr(request.difficulty, 'value') else str(request.difficulty)

    result = await gen.generate(
        units=units,
        quiz_type=quiz_type,
        difficulty=difficulty,
        num_questions=request.num_questions,
        topic=request.topic,
        source_title=source.title,
    )
    result['source_id'] = request.source_id
    return result


@router.post('/api/flashcards')
async def generate_flashcards(request: FlashcardRequest, db: AsyncSession = Depends(get_db)):
    """Generate flashcard pairs from a source's knowledge units."""
    settings = get_settings()
    source = await _get_source_or_404(request.source_id, db)
    units = await _load_units(request.source_id, db)

    if not units:
        raise HTTPException(status_code=422, detail='No knowledge units found. Has processing completed?')

    from app.generation.llm import LLMClient
    from app.generation.summary import FlashcardGenerator
    llm = LLMClient(settings)
    gen = FlashcardGenerator(llm)

    result = await gen.generate(
        units=units,
        num_cards=request.num_cards,
        topic=request.topic,
        source_title=source.title,
    )
    result['source_id'] = request.source_id
    return result


@router.post('/api/notes')
async def generate_notes(request: NotesRequest, db: AsyncSession = Depends(get_db)):
    """Generate study notes from a source's knowledge units."""
    settings = get_settings()
    source = await _get_source_or_404(request.source_id, db)
    units = await _load_units(request.source_id, db)

    if not units:
        raise HTTPException(status_code=422, detail='No knowledge units found. Has processing completed?')

    from app.generation.llm import LLMClient
    from app.generation.summary import NotesGenerator
    llm = LLMClient(settings)
    gen = NotesGenerator(llm)

    notes_type = request.notes_type.value if hasattr(request.notes_type, 'value') else str(request.notes_type)

    result = await gen.generate(
        units=units,
        notes_type=notes_type,
        topic=request.topic,
        source_title=source.title,
    )
    result['source_id'] = request.source_id
    return result
