"""
Query, source, and knowledge endpoints for VisionRAG-X.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import get_settings
from app.database.postgres import get_db
from app.knowledge.models import KnowledgeUnit, Source, Conflict, Evidence
from app.schemas.requests import QueryRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/api/query')
async def query(request: QueryRequest, db: AsyncSession = Depends(get_db)):
    """
    Run the full RAG pipeline for a query against a source.

    Returns: answer with citations, evidence items, detected conflicts,
    retrieval strategy used, and latency.
    """
    settings = get_settings()

    # Verify source exists and is completed
    result = await db.execute(select(Source).where(Source.id == request.source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f'Source {request.source_id} not found')
    if source.status not in ('completed', 'failed'):
        raise HTTPException(status_code=409, detail=f'Source processing is not complete (status: {source.status})')

    # Load knowledge units from DB
    ku_result = await db.execute(
        select(KnowledgeUnit)
        .where(KnowledgeUnit.source_id == request.source_id)
        .where(KnowledgeUnit.status != 'superseded')
        .limit(500)
    )
    units = ku_result.scalars().all()
    units_as_dicts = [_ku_to_dict(u) for u in units]
    units_by_id = {u['id']: u for u in units_as_dicts}

    # Load conflicts
    conflict_result = await db.execute(
        select(Conflict).where(Conflict.source_id == request.source_id)
    )
    conflicts = [_conflict_to_dict(c) for c in conflict_result.scalars().all()]

    # Build pipeline components
    from app.database.qdrant import QdrantManager
    from app.indexing.vector_index import VectorIndex
    from app.indexing.lexical_index import LexicalIndex
    from app.indexing.hybrid_index import HybridIndex
    from app.routing.dynamic_router import DynamicRouter
    from app.retrieval.retrieval_pipeline import Retriever, Reranker, RetrievalPipeline
    from app.verification.provenance import ProvenanceTracker
    from app.generation.llm import LLMClient
    from app.generation.answer import AnswerGenerator

    qdrant = QdrantManager(settings)
    vector_idx = VectorIndex(settings, qdrant)
    lexical_idx = LexicalIndex()
    lexical_idx.build_index(units_as_dicts)

    hybrid = HybridIndex(
        vector_idx, lexical_idx,
        alpha=settings.retrieval_alpha,
        beta=settings.retrieval_beta,
        gamma=settings.retrieval_gamma,
    )
    router_obj = DynamicRouter()
    retriever = Retriever(hybrid, vekg=None, settings=settings)
    reranker = Reranker()
    provenance = ProvenanceTracker()
    pipeline = RetrievalPipeline(router_obj, retriever, reranker, provenance, settings)

    pipeline_result = await pipeline.run(
        query=request.query,
        source_id=request.source_id,
        source_type=source.source_type or 'unknown',
        top_k=request.top_k,
        include_conflicts=request.include_conflicts,
        conflicts=conflicts,
        units_by_id=units_by_id,
    )

    # Generate answer
    llm = LLMClient(settings)
    answer_gen = AnswerGenerator(llm, provenance)
    try:
        answer_result = await answer_gen.generate(
            query=request.query,
            evidence=pipeline_result['evidence'],
            conflicts=pipeline_result['conflicts'],
            source_title=source.title,
        )
        answer_text = answer_result['answer']
        confidence = answer_result['confidence']
    except Exception as e:
        logger.warning('LLM answer generation failed: %s', e)
        from app.generation.llm import friendly_llm_error
        answer_text = (
            f'{friendly_llm_error(e)}\n\n'
            'Here is the verified evidence this answer would have been based on:\n' +
            '\n'.join(f'- {ev["text"][:200]}' for ev in pipeline_result['evidence'][:3])
        )
        confidence = 0.0

    # Build conflict response objects
    conflict_responses = []
    if request.include_conflicts:
        for i, c in enumerate(pipeline_result.get('conflicts', [])[:5]):
            conflict_responses.append({
                'conflict_id': f'conflict_{i}',
                'conflict_type': c.get('type', 'unknown'),
                'sources': c.get('sources', []),
                'claims': c.get('claims', []),
                'timestamp': c.get('timestamp'),
                'page': c.get('page'),
                'severity': c.get('severity', 'low'),
                'confidence': c.get('confidence', 0.5),
            })

    return {
        'answer': answer_text,
        'query': request.query,
        'source_id': request.source_id,
        'evidence': pipeline_result['evidence'] if request.include_evidence else [],
        'conflicts': conflict_responses,
        'confidence': confidence,
        'latency_ms': pipeline_result['latency_ms'],
        'retrieval_strategy_used': pipeline_result['strategy_used'],
    }


@router.get('/api/sources')
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all ingested sources, ordered by latest created."""
    result = await db.execute(
        select(Source).order_by(Source.created_at.desc()).limit(20)
    )
    sources = result.scalars().all()
    return [
        {
            'id': s.id,
            'title': s.title,
            'source_type': s.source_type,
            'status': s.status,
            'created_at': s.created_at.isoformat() if s.created_at else None,
        }
        for s in sources
    ]


@router.get('/api/source/{source_id}')
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Get metadata for a specific source."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f'Source {source_id} not found')
    return {
        'id': source.id,
        'title': source.title,
        'source_type': source.source_type,
        'status': source.status,
        'url': source.url,
        'file_path': source.file_path,
        'duration': source.duration,
        'num_pages': source.num_pages,
        'channel': source.channel,
        'upload_date': source.upload_date,
        'metadata': source.metadata_ or {},
        'created_at': source.created_at.isoformat() if source.created_at else None,
    }


@router.delete('/api/source/{source_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """
    Permanently delete a source and everything derived from it: its
    processing job, knowledge units, and conflicts (DB cascade), its vectors
    in Qdrant, and its uploaded file on disk.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f'Source {source_id} not found')

    try:
        settings = get_settings()
        from app.database.qdrant import QdrantManager
        from app.indexing.vector_index import VectorIndex
        qdrant = QdrantManager(settings)
        vector_idx = VectorIndex(settings, qdrant)
        await vector_idx.delete_by_source(source_id)
    except Exception as e:
        logger.warning('Failed to delete vectors for source %s (continuing): %s', source_id, e)

    if source.file_path:
        try:
            import shutil
            from pathlib import Path
            file_path = Path(source.file_path)
            source_dir = file_path.parent
            if source_dir.exists() and source_dir.name == source_id:
                shutil.rmtree(source_dir, ignore_errors=True)
            elif file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning('Failed to delete files for source %s (continuing): %s', source_id, e)

    await db.delete(source)
    await db.commit()
    logger.info('Deleted source %s and all derived data', source_id)


@router.get('/api/knowledge/{source_id}')
async def get_knowledge(source_id: str, db: AsyncSession = Depends(get_db)):
    """Get all knowledge units for a source."""
    result = await db.execute(
        select(KnowledgeUnit)
        .where(KnowledgeUnit.source_id == source_id)
        .order_by(KnowledgeUnit.timestamp_start.asc().nullsfirst())
        .limit(1000)
    )
    units = result.scalars().all()

    ev_result = await db.execute(
        select(Evidence.knowledge_unit_id, func.count(Evidence.id))
        .where(Evidence.knowledge_unit_id.in_([u.id for u in units]))
        .group_by(Evidence.knowledge_unit_id)
    )
    evidence_counts = dict(ev_result.all())

    return [
        {
            'id': u.id,
            'concept': u.concept,
            'content': u.content,
            'modality': u.modality,
            'source_id': u.source_id,
            'timestamp_start': u.timestamp_start,
            'timestamp_end': u.timestamp_end,
            'page': u.page,
            'slide': u.slide,
            'confidence': u.confidence,
            'status': u.status,
            'version': u.version,
            'previous_version_id': u.previous_version_id,
            'correction_reason': u.correction_reason,
            'evidence_count': evidence_counts.get(u.id, 0),
            'conflict_count': 0,
        }
        for u in units
    ]


@router.get('/api/knowledge/unit/{ku_id}/history')
async def get_knowledge_unit_history(ku_id: str, db: AsyncSession = Depends(get_db)):
    """
    Walk a knowledge unit's version chain (VKEG) — every earlier version it
    supersedes and every later version that supersedes it, oldest first.
    """
    result = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.id == ku_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail=f'Knowledge unit {ku_id} not found')

    chain = [unit]
    cursor = unit
    while cursor.previous_version_id:
        r = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.id == cursor.previous_version_id))
        prev = r.scalar_one_or_none()
        if not prev:
            break
        chain.append(prev)
        cursor = prev
    chain.reverse()  # oldest -> newest

    cursor = unit
    while True:
        r = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.previous_version_id == cursor.id))
        newer = r.scalar_one_or_none()
        if not newer:
            break
        chain.append(newer)
        cursor = newer

    return {
        'concept': unit.concept,
        'source_id': unit.source_id,
        'versions': [_ku_to_dict(u) for u in chain],
    }


@router.get('/api/knowledge/unit/{ku_id}/evidence')
async def get_knowledge_unit_evidence(ku_id: str, db: AsyncSession = Depends(get_db)):
    """All raw evidence segments (ASR/OCR/formula/code) supporting a knowledge unit."""
    result = await db.execute(select(Evidence).where(Evidence.knowledge_unit_id == ku_id))
    items = result.scalars().all()
    return [
        {
            'id': e.id,
            'text': e.text,
            'modality': e.modality,
            'source_id': e.source_id,
            'timestamp_start': e.timestamp_start,
            'timestamp_end': e.timestamp_end,
            'page': e.page,
            'confidence': e.extraction_confidence,
        }
        for e in items
    ]


@router.get('/api/source/{source_id}/conflicts')
async def get_source_conflicts(source_id: str, db: AsyncSession = Depends(get_db)):
    """All detected cross-modal conflicts for a source."""
    result = await db.execute(select(Conflict).where(Conflict.source_id == source_id))
    items = result.scalars().all()
    return [
        {
            'id': c.id,
            'conflict_type': c.conflict_type,
            'sources': c.modalities or [],
            'claims': c.claims or [],
            'timestamp': c.timestamp,
            'page': c.page,
            'severity': c.severity,
            'confidence': c.confidence,
            'resolved': c.resolved,
        }
        for c in items
    ]


@router.get('/api/source/{source_id}/evolution')
async def get_source_evolution(source_id: str, db: AsyncSession = Depends(get_db)):
    """
    Every real correction/version chain (length > 1) detected for a source —
    what the frontend Knowledge Evolution page renders.
    """
    result = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.source_id == source_id))
    units = result.scalars().all()

    children_of: dict = {}
    for u in units:
        if u.previous_version_id:
            children_of.setdefault(u.previous_version_id, []).append(u)

    chains = []
    for u in units:
        if u.previous_version_id is None and u.id in children_of:
            chain = [u]
            cursor = u
            while cursor.id in children_of:
                nxt = children_of[cursor.id][0]
                chain.append(nxt)
                cursor = nxt
            chains.append({
                'concept': u.concept,
                'source_id': source_id,
                'versions': [_ku_to_dict(v) for v in chain],
            })

    return chains


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ku_to_dict(u: KnowledgeUnit) -> dict:
    return {
        'id': u.id, 'concept': u.concept, 'content': u.content,
        'modality': u.modality, 'source_id': u.source_id,
        'timestamp_start': u.timestamp_start, 'timestamp_end': u.timestamp_end,
        'page': u.page, 'slide': u.slide, 'confidence': u.confidence,
        'status': u.status, 'version': u.version,
        'previous_version_id': u.previous_version_id,
        'correction_reason': u.correction_reason,
    }


def _conflict_to_dict(c: Conflict) -> dict:
    return {
        'type': c.conflict_type, 'sources': c.modalities or [],
        'claims': c.claims or [], 'timestamp': c.timestamp,
        'page': c.page, 'severity': c.severity, 'confidence': c.confidence,
    }
