"""
VisionRAG-X FastAPI Application Entry Point.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()

    # Create data directories
    for d in [settings.upload_dir, settings.frames_dir,
              settings.transcripts_dir, settings.processed_dir]:
        Path(d).mkdir(parents=True, exist_ok=True)
    logger.info('Data directories ready')

    # Initialize database
    try:
        from app.database.postgres import init_db
        await init_db()
        logger.info('PostgreSQL schema initialized')
    except Exception as e:
        logger.error('Database initialization failed (app may not function): %s', e)

    # Initialize Qdrant collection
    try:
        from app.database.qdrant import QdrantManager
        qdrant = QdrantManager(settings)
        await qdrant.init_collection()
        logger.info('Qdrant collection ready')
    except Exception as e:
        logger.error('Qdrant initialization failed (vector search unavailable): %s', e)

    logger.info('VisionRAG-X v0.1.0 started — docs at /docs')
    yield
    logger.info('VisionRAG-X shutting down')


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title='VisionRAG-X API',
    description=(
        'Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval '
        'from Educational Content.\n\n'
        '⚠️ **EXPERIMENTAL**: This is a research prototype. All novel components '
        '(VKEG, conflict detection, hybrid indexing, dynamic routing) are experimental '
        'and have not been formally evaluated.'
    ),
    version='0.1.0',
    lifespan=lifespan,
    docs_url='/docs',
    redoc_url='/redoc',
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error('Unhandled exception on %s: %s', request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'error': 'Internal server error', 'detail': str(exc)},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from app.api import health, upload, query, summary  # noqa: E402

app.include_router(health.router, tags=['Health'])
app.include_router(upload.router, tags=['Ingestion'])
app.include_router(query.router, tags=['Query & Knowledge'])
app.include_router(summary.router, tags=['Generation'])


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get('/', tags=['Root'])
async def root():
    return {
        'name': 'VisionRAG-X API',
        'version': '0.1.0',
        'status': 'running',
        'docs': '/docs',
        'health': '/api/health',
        'note': 'Research prototype — experimental components not yet formally evaluated.',
    }
