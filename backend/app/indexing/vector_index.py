"""
Vector index using sentence-transformers + Qdrant for VisionRAG-X.
Embedding model is fully configurable via EMBEDDING_MODEL env var.
"""
import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Process-wide cache keyed by "model_name:device" — a fresh VectorIndex is
# instantiated on every request (see app/api/query.py), so without this the
# ~440MB embedding model was being reloaded from disk on every single query.
_MODEL_CACHE: Dict[str, Any] = {}


class ConfigurationError(Exception):
    """Raised when a required model or service is not configured."""
    pass


class VectorIndex:
    """
    Semantic vector index backed by sentence-transformers and Qdrant.

    Embedding model is selected via the EMBEDDING_MODEL environment variable.
    Default: BAAI/bge-base-en-v1.5 (768-dim).

    The model is lazily loaded on first use to avoid startup overhead
    when the service is running without GPU.
    """

    def __init__(self, settings: Any, qdrant_manager: Any):
        self.settings = settings
        self.qdrant = qdrant_manager
        self._model = None
        self._vector_size: Optional[int] = None
        self._available: Optional[bool] = None

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def _check_availability(self) -> bool:
        if self._available is None:
            try:
                from sentence_transformers import SentenceTransformer  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def _load_model(self) -> None:
        if not self._check_availability():
            raise ConfigurationError(
                'sentence-transformers is not installed. '
                'Install with: pip install sentence-transformers torch'
            )
        if self._model is not None:
            return

        model_name = self.settings.embedding_model
        device = self.settings.embedding_device
        cache_key = f'{model_name}:{device}'

        if cache_key not in _MODEL_CACHE:
            from sentence_transformers import SentenceTransformer
            logger.info('Loading embedding model: %s on %s', model_name, device)
            model = SentenceTransformer(model_name, device=device)
            # Detect vector size from a test encode
            test_vec = model.encode(['test'])
            _MODEL_CACHE[cache_key] = (model, len(test_vec[0]))
            logger.info('Embedding model loaded. Vector size: %d', len(test_vec[0]))

        self._model, self._vector_size = _MODEL_CACHE[cache_key]

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Blocking implementation — always call via embed(), never directly from async code."""
        self._load_model()
        if not texts:
            return []
        batch_size = 32
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            vecs = self._model.encode(batch, show_progress_bar=False, normalize_embeddings=True)
            all_embeddings.extend(vecs.tolist())
        return all_embeddings

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of texts into embedding vectors.

        Runs the (CPU-bound, synchronous) model load + encode in a thread
        executor so it never blocks the asyncio event loop — otherwise a
        cold model load or a large batch freezes every other in-flight
        request (health checks, other users' queries) for its duration.

        Parameters
        ----------
        texts : list of str
            Texts to encode.

        Returns
        -------
        List of embedding vectors (list of floats).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._embed_sync, texts)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_units(self, units: List[Dict[str, Any]]) -> None:
        """
        Generate embeddings and upsert all units into Qdrant.

        Each unit dict must have at least: id, content, source_id, modality,
        confidence, status, concept.
        """
        if not units:
            return
        texts = [u.get('content', '') for u in units]
        embeddings = await self.embed(texts)

        from qdrant_client.models import PointStruct
        points: List[PointStruct] = []
        for unit, vector in zip(units, embeddings):
            point_id = str(uuid.uuid4())
            # Store the unit's DB id in the payload so we can retrieve it
            payload = {
                'knowledge_unit_id': unit.get('id', ''),
                'source_id': unit.get('source_id', ''),
                'modality': unit.get('modality', 'unknown'),
                'timestamp_start': unit.get('timestamp_start'),
                'timestamp_end': unit.get('timestamp_end'),
                'page': unit.get('page'),
                'slide': unit.get('slide'),
                'confidence': unit.get('confidence', 0.5),
                'status': unit.get('status', 'active'),
                'concept': unit.get('concept', ''),
                'content_preview': unit.get('content', '')[:200],
            }
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))
            # Update the unit with its Qdrant point ID
            unit['embedding_id'] = point_id

        await self.qdrant.upsert_vectors(points)
        logger.info('Indexed %d units into Qdrant', len(points))

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        source_id: Optional[str] = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search: embed query and search Qdrant.

        Returns list of dicts: {unit_id, score, payload}.
        """
        query_vec = (await self.embed([query]))[0]
        results = await self.qdrant.search(
            query_vector=query_vec,
            source_id_filter=source_id,
            limit=top_k,
            score_threshold=score_threshold,
        )
        return [
            {
                'unit_id': r['payload'].get('knowledge_unit_id', ''),
                'score': r['score'],
                'payload': r['payload'],
            }
            for r in results
        ]

    async def delete_by_source(self, source_id: str) -> None:
        """Remove all vectors belonging to a given source."""
        await self.qdrant.delete_by_source(source_id)
        logger.info('Deleted vectors for source %s', source_id)

    async def health_check(self) -> Dict[str, Any]:
        available = self._check_availability()
        return {
            'available': available,
            'model': self.settings.embedding_model,
            'device': self.settings.embedding_device,
            'vector_size': self._vector_size,
            'error': None if available else 'sentence-transformers not installed',
        }
