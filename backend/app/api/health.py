"""
Health check endpoint for VisionRAG-X.
"""
import time
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database.postgres import check_db_health
from app.database.qdrant import QdrantManager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/api/health', tags=['Health'])
async def health_check():
    """
    System health check.

    Returns connectivity status for all components:
    - PostgreSQL database
    - Qdrant vector store
    - LLM provider
    - Embedding model

    Always returns HTTP 200; use the 'status' field to determine health.
    """
    settings = get_settings()
    components = {}

    # --- Database ---
    components['database'] = await check_db_health()

    # --- Qdrant ---
    try:
        qdrant = QdrantManager(settings)
        components['qdrant'] = await qdrant.health_check()
    except Exception as e:
        components['qdrant'] = {'available': False, 'error': str(e)}

    # --- LLM ---
    try:
        from app.generation.llm import LLMClient
        llm = LLMClient(settings)
        components['llm'] = await llm.health_check()
    except Exception as e:
        components['llm'] = {'available': False, 'error': str(e)}

    # --- Embedding model ---
    try:
        from app.indexing.vector_index import VectorIndex
        vi = VectorIndex(settings, None)
        components['embedding'] = await vi.health_check()
    except Exception as e:
        components['embedding'] = {'available': False, 'error': str(e)}

    # Overall status
    available_flags = [v.get('available', False) for v in components.values()]
    if all(available_flags):
        overall = 'healthy'
    elif any(available_flags):
        overall = 'degraded'
    else:
        overall = 'unhealthy'

    return JSONResponse({
        'status': overall,
        'version': '0.1.0',
        'components': components,
    })
