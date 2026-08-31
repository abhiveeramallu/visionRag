"""
Query, source, and knowledge endpoints for VisionRAG-X.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database.postgres import get_db
from app.knowledge.models import KnowledgeUnit, Source, Conflict
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
        answer_text = (
            f'[LLM not configured or unavailable: {e}]\n\n'
            'Retrieved evidence:\n' +
            '\n'.join(f'- {e["text"][:200]}' for e in pipeline_result['evidence'][:3])
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
            'correction_reason': u.correction_reason,
            'evidence_count': 0,
            'conflict_count': 0,
        }
        for u in units
    ]


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
        'correction_reason': u.correction_reason,
    }


def _conflict_to_dict(c: Conflict) -> dict:
    return {
        'type': c.conflict_type, 'sources': c.modalities or [],
        'claims': c.claims or [], 'timestamp': c.timestamp,
        'page': c.page, 'severity': c.severity, 'confidence': c.confidence,
    }
