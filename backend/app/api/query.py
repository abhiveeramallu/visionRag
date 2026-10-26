"""
Query, source, and knowledge endpoints for VisionRAG-X.
"""
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.config import get_settings
from app.database.postgres import get_db
from app.knowledge.models import KnowledgeUnit, Source, Conflict, Evidence, ChatConversation, ChatMessage
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
    if not request.source_id or not request.source_id.strip():
        raise HTTPException(status_code=400, detail='source_id is required')

    settings = get_settings()

    # Verify source exists and is completed
    result = await db.execute(select(Source).where(Source.id == request.source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f'Source {request.source_id} not found')
    if source.status != 'completed':
        raise HTTPException(status_code=409, detail=f'Source processing is not complete (status: {source.status})')

    # Load all knowledge units from DB for this source (for VEKG reconstruction)
    ku_result = await db.execute(
        select(KnowledgeUnit)
        .where(KnowledgeUnit.source_id == request.source_id)
        .order_by(KnowledgeUnit.created_at.asc())
        .limit(2000)
    )
    units = ku_result.scalars().all()
    if len(units) >= 2000:
        logger.warning('Source %s exceeded 2000 active knowledge units; retrieved top 2000', request.source_id)
    units_as_dicts = [_ku_to_dict(u) for u in units]
    units_by_id = {u['id']: u for u in units_as_dicts}

    # Load conflicts
    conflict_result = await db.execute(
        select(Conflict).where(Conflict.source_id == request.source_id)
    )
    conflicts = [_conflict_to_dict(c) for c in conflict_result.scalars().all()]

    # Resolve or create conversation session for this source
    conv = None
    conv_id = request.conversation_id
    if request.save_history:
        try:
            if conv_id:
                c_res = await db.execute(
                    select(ChatConversation).where(ChatConversation.id == conv_id)
                )
                conv = c_res.scalar_one_or_none()
                if conv and conv.source_id != request.source_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f'Conversation {conv_id} does not belong to source {request.source_id}',
                    )
            if not conv:
                c_res = await db.execute(
                    select(ChatConversation)
                    .where(ChatConversation.source_id == request.source_id)
                    .order_by(ChatConversation.updated_at.desc())
                    .limit(1)
                )
                conv = c_res.scalar_one_or_none()
            if not conv:
                conv = ChatConversation(source_id=request.source_id, title=source.title[:120])
                db.add(conv)
                await db.flush()
            conv_id = conv.id
        except (StopIteration, HTTPException):
            raise
        except Exception as e:
            logger.warning('Failed resolving conversation session: %s', e)

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
    from app.knowledge.vekg import VEKG
    from app.knowledge.knowledge_units import ProcessedKnowledgeUnit

    # Reconstruct in-memory VEKG for this source including lineage edges and conflicts
    pku_units = [
        ProcessedKnowledgeUnit(
            id=u.id,
            concept=u.concept,
            content=u.content,
            modality=u.modality,
            source_id=u.source_id,
            timestamp_start=u.timestamp_start,
            timestamp_end=u.timestamp_end,
            page=u.page,
            slide=u.slide,
            confidence=u.confidence,
            status=u.status,
            version=u.version,
            previous_version_id=u.previous_version_id,
            correction_reason=u.correction_reason,
        )
        for u in units
    ]
    vekg = VEKG()
    vekg.reconstruct_from_units(pku_units, conflicts=conflicts)

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
    retriever = Retriever(hybrid, vekg=vekg, settings=settings)
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
            abstain=pipeline_result.get('abstain', False),
        )
        answer_text = answer_result['answer']
        confidence = answer_result['confidence']
    except Exception as e:
        logger.warning('LLM answer generation failed: %s', e)
        from app.generation.llm import friendly_llm_error
        status_msg = friendly_llm_error(e)
        evidence_snippets = [f'- {ev["text"][:200]}' for ev in pipeline_result.get('evidence', [])[:3]]
        if 'Retrieved evidence is shown below' in status_msg:
            if evidence_snippets:
                answer_text = f'{status_msg}\n\n' + '\n'.join(evidence_snippets)
            else:
                answer_text = status_msg
        else:
            if evidence_snippets:
                answer_text = f'{status_msg} Retrieved evidence is shown below:\n\n' + '\n'.join(evidence_snippets)
            else:
                answer_text = status_msg
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
                'status': c.get('status', 'candidate' if c.get('is_candidate') else 'unresolved'),
                'is_genuine_conflict': c.get('is_genuine_conflict'),
                'verification_status': c.get('verification_status', 'unverified'),
                'resolution': c.get('resolution'),
            })

    trace = {
        'query': request.query,
        'routing': {
            'query_type': pipeline_result.get('query_type'),
            'strategy_used': str(pipeline_result.get('strategy_used', 'hybrid')),
            'explanation': pipeline_result.get('routing_explanation'),
        },
        'candidates': {
            'dense_count': len(pipeline_result.get('evidence', [])),
            'lexical_count': len(units_as_dicts),
            'selected_evidence_count': len(pipeline_result.get('evidence', [])),
        },
        'lineage_resolution': {
            'applied': len(pipeline_result.get('lineage_substitutions', [])) > 0,
            'substitutions': pipeline_result.get('lineage_substitutions', []),
        },
        'conflicts': {
            'total_detected': len(conflict_responses),
            'items': conflict_responses,
        },
        'sufficiency_gate': {
            'abstained': pipeline_result.get('abstain', False),
            'reason': pipeline_result.get('abstention_reason') or (
                'Grounded subject overlap verified' if not pipeline_result.get('abstain') else 'Insufficient grounding evidence'
            ),
        },
        'latency_ms': pipeline_result['latency_ms'],
    }

    # Persist message turns to the source-specific conversation
    if request.save_history and conv:
        try:
            from datetime import datetime
            user_msg = ChatMessage(
                conversation_id=conv.id,
                source_id=request.source_id,
                role='user',
                content=request.query,
            )
            asst_msg = ChatMessage(
                conversation_id=conv.id,
                source_id=request.source_id,
                role='assistant',
                content=answer_text,
                evidence=pipeline_result['evidence'] if request.include_evidence else [],
                conflicts=conflict_responses,
                trace=trace,
                confidence=confidence,
                strategy=pipeline_result['strategy_used'],
                abstained=pipeline_result.get('abstain', False),
                latency_ms=pipeline_result['latency_ms'],
            )
            conv.updated_at = datetime.utcnow()
            db.add(user_msg)
            db.add(asst_msg)
            await db.commit()
        except StopIteration:
            pass
        except Exception as e:
            logger.warning('Failed persisting chat message: %s', e)

    return {
        'answer': answer_text,
        'query': request.query,
        'source_id': request.source_id,
        'conversation_id': conv_id,
        'evidence': pipeline_result['evidence'] if request.include_evidence else [],
        'conflicts': conflict_responses,
        'confidence': confidence,
        'latency_ms': pipeline_result['latency_ms'],
        'retrieval_strategy_used': pipeline_result['strategy_used'],
        'abstained': pipeline_result.get('abstain', False),
        'trace': trace,
    }


# ---------------------------------------------------------------------------
# Source-Isolated AI Chat Endpoints
# ---------------------------------------------------------------------------

@router.get('/api/chat/sources/{source_id}/conversation')
async def get_or_create_source_conversation(
    source_id: str,
    conversation_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the conversation session and chronological message history for a source.
    If no conversation exists yet, a new session is started.
    """
    if not source_id or not source_id.strip():
        raise HTTPException(status_code=400, detail='source_id is required')

    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f'Source {source_id} not found')
    if source.status != 'completed':
        raise HTTPException(status_code=409, detail=f'Source processing is not complete (status: {source.status})')

    conv = None
    if conversation_id:
        c_res = await db.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id)
        )
        conv = c_res.scalar_one_or_none()
        if conv and conv.source_id != source_id:
            raise HTTPException(
                status_code=400,
                detail=f'Conversation {conversation_id} does not belong to source {source_id}',
            )

    if not conv:
        c_res = await db.execute(
            select(ChatConversation)
            .where(ChatConversation.source_id == source_id)
            .order_by(ChatConversation.updated_at.desc())
            .limit(1)
        )
        conv = c_res.scalar_one_or_none()

    if not conv:
        conv = ChatConversation(source_id=source_id, title=source.title[:120])
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

    m_res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = m_res.scalars().all()

    return {
        'id': conv.id,
        'source_id': conv.source_id,
        'source_title': source.title,
        'source_status': source.status,
        'title': conv.title,
        'created_at': conv.created_at.isoformat() if conv.created_at else None,
        'updated_at': conv.updated_at.isoformat() if conv.updated_at else None,
        'messages': [
            {
                'id': m.id,
                'conversation_id': m.conversation_id,
                'source_id': m.source_id,
                'role': m.role,
                'content': m.content,
                'evidence': m.evidence or [],
                'conflicts': m.conflicts or [],
                'trace': m.trace or {},
                'confidence': m.confidence,
                'strategy': m.strategy,
                'abstained': m.abstained,
                'latency_ms': m.latency_ms,
                'created_at': m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post('/api/chat/sources/{source_id}/conversation/new')
async def create_new_source_conversation(
    source_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a fresh, empty AI Chat session scoped to the selected source.
    """
    if not source_id or not source_id.strip():
        raise HTTPException(status_code=400, detail='source_id is required')

    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f'Source {source_id} not found')
    if source.status != 'completed':
        raise HTTPException(status_code=409, detail=f'Source processing is not complete (status: {source.status})')

    conv = ChatConversation(source_id=source_id, title=source.title[:120])
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return {
        'id': conv.id,
        'source_id': conv.source_id,
        'source_title': source.title,
        'source_status': source.status,
        'title': conv.title,
        'created_at': conv.created_at.isoformat() if conv.created_at else None,
        'updated_at': conv.updated_at.isoformat() if conv.updated_at else None,
        'messages': [],
    }


@router.get('/api/chat/sources/{source_id}/suggested-questions')
async def get_suggested_questions(
    source_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Context-aware suggested questions based on the source's actual indexed concepts.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f'Source {source_id} not found')

    ku_res = await db.execute(
        select(KnowledgeUnit)
        .where(KnowledgeUnit.source_id == source_id)
        .order_by(KnowledgeUnit.confidence.desc())
        .limit(10)
    )
    units = ku_res.scalars().all()

    questions = []
    seen = set()
    for u in units:
        c = u.concept.strip()
        if c and c.lower() not in seen:
            seen.add(c.lower())
            if u.modality == 'formula':
                questions.append(f'What formula is used for {c}?')
            elif u.modality == 'code':
                questions.append(f'How is {c} implemented in code?')
            else:
                questions.append(f'Explain {c} based on this lecture.')
        if len(questions) >= 4:
            break

    if len(questions) < 4:
        fallback_templates = [
            f'Summarize the core arguments in {source.title}.',
            'What formulas or equations were derived?',
            'What mistakes or errata were corrected?',
            'List the key concepts covered in this material.',
        ]
        for fb in fallback_templates:
            if fb not in questions:
                questions.append(fb)
            if len(questions) >= 4:
                break

    return {'source_id': source_id, 'questions': questions[:6]}


@router.get('/api/chat/sources/{source_id}/conversations')
async def list_source_conversations(
    source_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List all conversation sessions belonging to a specific source.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f'Source {source_id} not found')

    c_res = await db.execute(
        select(ChatConversation)
        .where(ChatConversation.source_id == source_id)
        .order_by(ChatConversation.updated_at.desc())
    )
    convs = c_res.scalars().all()

    items = []
    for c in convs:
        cnt_res = await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.conversation_id == c.id)
        )
        msg_count = cnt_res.scalar() or 0
        items.append({
            'id': c.id,
            'source_id': c.source_id,
            'title': c.title,
            'message_count': msg_count,
            'created_at': c.created_at.isoformat() if c.created_at else None,
            'updated_at': c.updated_at.isoformat() if c.updated_at else None,
        })

    return items


@router.delete('/api/chat/conversations/{conversation_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a specific conversation session and its messages."""
    result = await db.execute(select(ChatConversation).where(ChatConversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail=f'Conversation {conversation_id} not found')
    await db.delete(conv)
    await db.commit()


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


@router.get('/api/knowledge-graph')
async def get_knowledge_graph(
    source_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full graph structure (nodes and real relationships) derived from
    persisted KnowledgeUnits, version corrections, and Conflicts.
    """
    # Fetch sources
    if source_id:
        src_query = select(Source).where(Source.id == source_id)
    else:
        src_query = select(Source).where(Source.status == 'completed')
    sources = (await db.execute(src_query)).scalars().all()
    source_map = {s.id: s.title for s in sources}
    source_ids = list(source_map.keys())

    if not source_ids:
        return {'nodes': [], 'edges': [], 'summary': {'total_nodes': 0, 'total_edges': 0, 'sources': 0}}

    # Fetch knowledge units
    ku_query = (
        select(KnowledgeUnit)
        .where(KnowledgeUnit.source_id.in_(source_ids))
        .order_by(KnowledgeUnit.page.asc().nullsfirst(), KnowledgeUnit.timestamp_start.asc().nullsfirst())
    )
    units = (await db.execute(ku_query)).scalars().all()

    # Evidence counts
    ev_counts = {}
    if units:
        ev_query = (
            select(Evidence.knowledge_unit_id, func.count(Evidence.id))
            .where(Evidence.knowledge_unit_id.in_([u.id for u in units]))
            .group_by(Evidence.knowledge_unit_id)
        )
        ev_counts = dict((await db.execute(ev_query)).all())

    # Fetch conflicts
    conf_query = select(Conflict).where(Conflict.source_id.in_(source_ids))
    conflicts = (await db.execute(conf_query)).scalars().all()

    # Build nodes
    nodes = []
    unit_map = {u.id: u for u in units}
    for u in units:
        nodes.append({
            'id': u.id,
            'label': u.concept,
            'concept': u.concept,
            'definition': u.content,
            'modality': u.modality,
            'source_id': u.source_id,
            'source_title': source_map.get(u.source_id, 'Source'),
            'page': u.page,
            'slide': u.slide,
            'timestamp_start': u.timestamp_start,
            'timestamp_end': u.timestamp_end,
            'confidence': round(u.confidence, 4) if u.confidence is not None else 0.5,
            'status': u.status,
            'version': u.version or 1,
            'previous_version_id': u.previous_version_id,
            'correction_reason': u.correction_reason,
            'evidence_count': ev_counts.get(u.id, 1),
        })

    # Build edges strictly from stored relationships
    edges = []
    edge_seen = set()

    # 1. Lineage / correction edges
    for u in units:
        if u.previous_version_id and u.previous_version_id in unit_map:
            prev_u = unit_map[u.previous_version_id]
            is_correction = bool(u.correction_reason or prev_u.status == 'superseded')
            rel = 'corrects' if is_correction else 'supersedes'
            edge_id = f'edge-lineage-{u.id}-{prev_u.id}'
            edges.append({
                'id': edge_id,
                'source': u.id,
                'target': prev_u.id,
                'relation': rel,
                'label': 'Corrects' if is_correction else 'Supersedes',
                'reason': u.correction_reason or 'Version update',
                'source_label': u.concept,
                'target_label': prev_u.concept,
            })
            edge_seen.add((u.id, prev_u.id))

    # 2. Conflict edges
    for c in conflicts:
        matched_uids = []
        c_page = c.page
        c_ts = c.timestamp
        for u in units:
            if u.source_id == c.source_id:
                if c_page is not None and (u.page == c_page or u.slide == c_page):
                    matched_uids.append(u.id)
                elif c_ts is not None and u.timestamp_start is not None and abs(c_ts - u.timestamp_start) <= 30.0:
                    matched_uids.append(u.id)

        if len(matched_uids) >= 2:
            u1, u2 = matched_uids[0], matched_uids[1]
            if (u1, u2) not in edge_seen and (u2, u1) not in edge_seen:
                edge_id = f'edge-conflict-{c.id}'
                edges.append({
                    'id': edge_id,
                    'source': u1,
                    'target': u2,
                    'relation': 'conflicts_with',
                    'label': 'Conflicts With',
                    'conflict_type': c.conflict_type,
                    'severity': c.severity,
                    'claims': c.claims or [],
                    'resolved': c.resolved,
                })
                edge_seen.add((u1, u2))

    # 3. Same-concept / topic associations (across distinct versions or pages)
    concept_groups = {}
    for u in units:
        norm_concept = u.concept.strip().lower()
        concept_groups.setdefault(norm_concept, []).append(u.id)

    for norm_c, uids in concept_groups.items():
        if len(uids) > 1:
            for i in range(len(uids) - 1):
                u_a, u_b = uids[i], uids[i + 1]
                if (u_a, u_b) not in edge_seen and (u_b, u_a) not in edge_seen:
                    edges.append({
                        'id': f'edge-rel-{u_a}-{u_b}',
                        'source': u_a,
                        'target': u_b,
                        'relation': 'related_to',
                        'label': 'Related Concept',
                    })
                    edge_seen.add((u_a, u_b))

    return {
        'nodes': nodes,
        'edges': edges,
        'summary': {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'sources': len(source_ids),
            'correction_edges': sum(1 for e in edges if e['relation'] in ('corrects', 'supersedes')),
            'conflict_edges': sum(1 for e in edges if e['relation'] == 'conflicts_with'),
        },
    }


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


def _find_repo_root() -> Path:
    """Find the visionrag-x repository root directory."""
    for candidate in [
        Path(__file__).resolve().parents[3],
        Path(__file__).resolve().parents[2],
        Path.cwd(),
        Path.cwd().parent,
    ]:
        if (candidate / 'evaluation').is_dir() and (candidate / 'backend').is_dir():
            return candidate
    return Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Knowledge Units Browser Endpoints
# ---------------------------------------------------------------------------

@router.get('/api/knowledge-units')
async def list_knowledge_units(
    source_id: Optional[str] = Query(None),
    modality: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Search and filter ingested Knowledge Units with pagination.
    Supports filtering by source, modality, lifecycle status, and keyword search.
    """
    conditions = []
    if source_id:
        conditions.append(KnowledgeUnit.source_id == source_id)
    if modality:
        conditions.append(KnowledgeUnit.modality == modality)
    if status:
        conditions.append(KnowledgeUnit.status == status)
    if search:
        search_filter = or_(
            KnowledgeUnit.concept.ilike(f'%{search}%'),
            KnowledgeUnit.content.ilike(f'%{search}%'),
        )
        conditions.append(search_filter)

    # Total count
    count_query = select(func.count(KnowledgeUnit.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total_count = (await db.execute(count_query)).scalar() or 0

    # Paged units
    data_query = (
        select(KnowledgeUnit)
        .order_by(KnowledgeUnit.created_at.desc(), KnowledgeUnit.id.asc())
        .offset(offset)
        .limit(limit)
    )
    if conditions:
        data_query = data_query.where(*conditions)
    units = (await db.execute(data_query)).scalars().all()

    if not units:
        return {'total': total_count, 'limit': limit, 'offset': offset, 'items': []}

    # Fetch source titles
    unit_source_ids = list({u.source_id for u in units if u.source_id})
    sources_result = await db.execute(select(Source).where(Source.id.in_(unit_source_ids)))
    source_map = {s.id: s.title for s in sources_result.scalars().all()}

    # Fetch evidence counts
    unit_ids = [u.id for u in units]
    ev_counts_result = await db.execute(
        select(Evidence.knowledge_unit_id, func.count(Evidence.id))
        .where(Evidence.knowledge_unit_id.in_(unit_ids))
        .group_by(Evidence.knowledge_unit_id)
    )
    ev_counts = dict(ev_counts_result.all())

    items = [
        {
            'id': u.id,
            'concept': u.concept,
            'content': u.content,
            'modality': u.modality,
            'source_id': u.source_id,
            'source_title': source_map.get(u.source_id, 'Source'),
            'timestamp_start': u.timestamp_start,
            'timestamp_end': u.timestamp_end,
            'page': u.page,
            'slide': u.slide,
            'confidence': round(u.confidence, 4) if u.confidence is not None else 0.5,
            'status': u.status,
            'version': u.version or 1,
            'previous_version_id': u.previous_version_id,
            'correction_reason': u.correction_reason,
            'evidence_count': ev_counts.get(u.id, 0),
            'created_at': u.created_at.isoformat() if u.created_at else None,
        }
        for u in units
    ]

    return {
        'total': total_count,
        'limit': limit,
        'offset': offset,
        'items': items,
    }


@router.get('/api/knowledge-units/{ku_id}')
async def get_knowledge_unit_detail(ku_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get comprehensive details for a single Knowledge Unit, including its
    source provenance, raw evidence items, full lineage version chain,
    and any associated cross-modal conflicts.
    """
    result = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.id == ku_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail=f'Knowledge unit {ku_id} not found')

    # Source info
    source_info = None
    if unit.source_id:
        src_res = await db.execute(select(Source).where(Source.id == unit.source_id))
        src = src_res.scalar_one_or_none()
        if src:
            source_info = {
                'id': src.id,
                'title': src.title,
                'source_type': src.source_type,
                'status': src.status,
                'url': src.url,
            }

    # Supporting evidence
    ev_res = await db.execute(
        select(Evidence)
        .where(Evidence.knowledge_unit_id == ku_id)
        .order_by(Evidence.extraction_confidence.desc().nullslast())
    )
    evidence_items = [
        {
            'id': e.id,
            'text': e.text,
            'modality': e.modality,
            'page': e.page,
            'timestamp_start': e.timestamp_start,
            'timestamp_end': e.timestamp_end,
            'confidence': round(e.extraction_confidence, 4) if e.extraction_confidence is not None else 0.5,
        }
        for e in ev_res.scalars().all()
    ]

    # Lineage chain (oldest -> newest)
    chain = [unit]
    cursor = unit
    visited = {unit.id}
    while cursor.previous_version_id and cursor.previous_version_id not in visited:
        visited.add(cursor.previous_version_id)
        r = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.id == cursor.previous_version_id))
        prev = r.scalar_one_or_none()
        if not prev:
            break
        chain.append(prev)
        cursor = prev
    chain.reverse()

    cursor = unit
    while True:
        r = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.previous_version_id == cursor.id))
        newer = r.scalar_one_or_none()
        if not newer or newer.id in visited:
            break
        visited.add(newer.id)
        chain.append(newer)
        cursor = newer

    lineage = [
        {
            'id': u.id,
            'version': u.version or 1,
            'concept': u.concept,
            'content': u.content,
            'modality': u.modality,
            'status': u.status,
            'page': u.page,
            'timestamp_start': u.timestamp_start,
            'correction_reason': u.correction_reason,
            'is_current': u.id == ku_id,
        }
        for u in chain
    ]

    # Associated conflicts
    conflicts = []
    if unit.source_id:
        c_res = await db.execute(select(Conflict).where(Conflict.source_id == unit.source_id))
        for c in c_res.scalars().all():
            matched = False
            if c.page is not None and unit.page is not None and c.page == unit.page:
                matched = True
            elif (
                c.timestamp is not None
                and unit.timestamp_start is not None
                and abs(c.timestamp - unit.timestamp_start) <= 30.0
            ):
                matched = True
            if matched:
                conflicts.append({
                    'id': c.id,
                    'conflict_type': c.conflict_type,
                    'sources': c.modalities or [],
                    'claims': c.claims or [],
                    'timestamp': c.timestamp,
                    'page': c.page,
                    'severity': c.severity,
                    'confidence': round(c.confidence, 4) if c.confidence is not None else 0.5,
                    'resolved': c.resolved,
                })

    return {
        'id': unit.id,
        'concept': unit.concept,
        'content': unit.content,
        'modality': unit.modality,
        'source_id': unit.source_id,
        'source': source_info,
        'timestamp_start': unit.timestamp_start,
        'timestamp_end': unit.timestamp_end,
        'page': unit.page,
        'slide': unit.slide,
        'confidence': round(unit.confidence, 4) if unit.confidence is not None else 0.5,
        'status': unit.status,
        'version': unit.version or 1,
        'previous_version_id': unit.previous_version_id,
        'correction_reason': unit.correction_reason,
        'created_at': unit.created_at.isoformat() if unit.created_at else None,
        'evidence': evidence_items,
        'lineage': lineage,
        'conflicts': conflicts,
    }


# ---------------------------------------------------------------------------
# Research Evaluation Endpoints
# ---------------------------------------------------------------------------

class EvaluationRunRequest(BaseModel):
    type: str = 'synthetic'  # 'synthetic' | 'real_video' | 'ablation'


@router.get('/api/evaluation/artifacts')
async def get_evaluation_artifacts():
    """
    Retrieve real evaluation benchmark artifacts and reports generated by
    the evaluation suite. Returns actual benchmark results, ablation matrices,
    and dataset metadata without mock or synthetic substitution.
    """
    root = _find_repo_root()
    eval_dir = root / 'evaluation'
    results_dir = eval_dir / 'results'
    bench_dir = eval_dir / 'benchmark'

    def _read_json(path: Path) -> Optional[Any]:
        if path.is_file():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error('Failed reading %s: %s', path, e)
        return None

    def _read_text(path: Path) -> Optional[str]:
        if path.is_file():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error('Failed reading %s: %s', path, e)
        return None

    # Benchmark datasets metadata
    synthetic_ds = _read_json(bench_dir / 'dataset.json')
    real_video_ds = _read_json(bench_dir / 'real_video_dataset.json')

    synthetic_meta = {}
    if synthetic_ds:
        synthetic_meta = {
            'corpus_count': len(synthetic_ds.get('corpus', [])),
            'conflicts_count': len(synthetic_ds.get('conflicts', [])),
            'questions_count': len(synthetic_ds.get('questions', [])),
            'categories': list({q.get('category') for q in synthetic_ds.get('questions', []) if q.get('category')}),
        }

    real_video_meta = {}
    if real_video_ds:
        real_video_meta = {
            'corpus_count': len(real_video_ds.get('corpus', [])),
            'conflicts_count': len(real_video_ds.get('conflicts', [])),
            'questions_count': len(real_video_ds.get('questions', [])),
            'categories': list({q.get('category') for q in real_video_ds.get('questions', []) if q.get('category')}),
        }

    # Results
    synthetic_results = _read_json(results_dir / 'evaluation_results.json')
    real_video_results = _read_json(results_dir / 'evaluation_results_real_video.json')
    ablation_results = _read_json(results_dir / 'ablation_results.json')

    # Reports
    synth_report = _read_text(results_dir / 'benchmark_report.md')
    real_report = _read_text(results_dir / 'benchmark_report_real_video.md')
    ablation_report = _read_text(results_dir / 'ablation_report.md')

    return {
        'benchmarks': {
            'synthetic': {
                'metadata': synthetic_meta,
                'results': synthetic_results or [],
                'report_md': synth_report or '',
                'questions': (synthetic_ds or {}).get('questions', []),
            },
            'real_video': {
                'metadata': real_video_meta,
                'results': real_video_results or [],
                'report_md': real_report or '',
                'questions': (real_video_ds or {}).get('questions', []),
            },
        },
        'ablations': {
            'conditions': ablation_results or [],
            'report_md': ablation_report or '',
        },
    }


@router.post('/api/evaluation/run')
async def run_evaluation(request: EvaluationRunRequest):
    """
    Execute an evaluation or ablation run locally and return execution logs.
    """
    valid_types = {'synthetic', 'real_video', 'ablation'}
    if request.type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f'Invalid evaluation type {request.type}. Expected one of {valid_types}',
        )

    root = _find_repo_root()
    start_time = time.time()

    if request.type == 'synthetic':
        cmd = [sys.executable, str(root / 'evaluation' / 'run_eval.py')]
    elif request.type == 'real_video':
        cmd = [
            sys.executable,
            str(root / 'evaluation' / 'run_eval.py'),
            '--dataset',
            str(root / 'evaluation' / 'benchmark' / 'real_video_dataset.json'),
            '--output-suffix',
            'real_video',
        ]
    else:  # ablation
        cmd = [sys.executable, str(root / 'evaluation' / 'run_ablations.py')]

    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(root),
        )
        stdout, stderr = await proc.communicate()
        duration = round(time.time() - start_time, 2)

        out_str = stdout.decode('utf-8', errors='replace')
        err_str = stderr.decode('utf-8', errors='replace')

        if proc.returncode != 0:
            logger.error('Evaluation run failed (%s): %s', proc.returncode, err_str)
            return {
                'status': 'error',
                'type': request.type,
                'exit_code': proc.returncode,
                'stdout': out_str,
                'stderr': err_str,
                'duration_seconds': duration,
            }

        return {
            'status': 'success',
            'type': request.type,
            'exit_code': 0,
            'stdout': out_str,
            'stderr': err_str,
            'duration_seconds': duration,
        }
    except Exception as e:
        logger.exception('Failed executing evaluation subprocess: %s', e)
        raise HTTPException(status_code=500, detail=f'Failed to execute evaluation: {str(e)}')
