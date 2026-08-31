"""
Qdrant vector store manager for VisionRAG-X.
Uses the official qdrant-client AsyncQdrantClient.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import Settings

logger = logging.getLogger(__name__)

# Map embedding model names to their output dimensions.
_EMBEDDING_DIMS: Dict[str, int] = {
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-small-en-v1.5": 384,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-mpnet-base-v2": 768,
}


def _infer_vector_size(model_name: str) -> int:
    return _EMBEDDING_DIMS.get(model_name, 768)


class QdrantManager:
    """
    Async Qdrant collection manager.

    All public methods are coroutines and must be awaited.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._collection = settings.qdrant_collection
        self._vector_size = _infer_vector_size(settings.embedding_model)

        kwargs: Dict[str, Any] = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            kwargs["api_key"] = settings.qdrant_api_key

        self.client: AsyncQdrantClient = AsyncQdrantClient(**kwargs)
        logger.info(
            "QdrantManager initialised: url=%s collection=%s vector_size=%d",
            settings.qdrant_url,
            self._collection,
            self._vector_size,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init_collection(self) -> None:
        """
        Ensure the target collection exists.
        Creates it with COSINE distance if absent; skips silently if present.
        """
        existing = [c.name for c in (await self.client.get_collections()).collections]
        if self._collection in existing:
            logger.info("Collection '%s' already exists – skipping creation.", self._collection)
            return

        await self.client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(
                size=self._vector_size,
                distance=Distance.COSINE,
            ),
        )
        logger.info(
            "Created Qdrant collection '%s' (dims=%d, COSINE).",
            self._collection,
            self._vector_size,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def upsert_vectors(self, points: List[PointStruct]) -> None:
        """
        Upsert a batch of PointStruct objects into the collection.

        Parameters
        ----------
        points:
            List of ``qdrant_client.http.models.PointStruct`` objects.
            Each point requires an ``id`` (str/int), ``vector`` (list[float]),
            and optionally a ``payload`` dict.
        """
        if not points:
            return
        await self.client.upsert(
            collection_name=self._collection,
            points=points,
            wait=True,
        )
        logger.debug("Upserted %d vectors into '%s'.", len(points), self._collection)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def search(
        self,
        query_vector: List[float],
        source_id_filter: Optional[str] = None,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Approximate nearest-neighbour search.

        Parameters
        ----------
        query_vector:
            Dense embedding of the query (must match collection dims).
        source_id_filter:
            If set, restrict results to vectors whose payload ``source_id``
            equals this value.
        limit:
            Maximum number of results to return.
        score_threshold:
            Drop results with cosine similarity below this value.

        Returns
        -------
        List of dicts with keys: id, score, payload.
        """
        query_filter: Optional[Filter] = None
        if source_id_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_id",
                        match=MatchValue(value=source_id_filter),
                    )
                ]
            )

        results = await self.client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload or {},
            }
            for hit in results
        ]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_by_source(self, source_id: str) -> None:
        """
        Delete all vectors whose payload ``source_id`` matches.

        Uses a filter-based delete (no need to know individual point IDs).
        """
        await self.client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="source_id",
                            match=MatchValue(value=source_id),
                        )
                    ]
                )
            ),
            wait=True,
        )
        logger.info("Deleted vectors for source_id='%s'.", source_id)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """
        Return a health dict compatible with ComponentStatus.

        Checks cluster reachability and reports collection-level stats.
        """
        try:
            t0 = time.monotonic()
            info = await self.client.get_collection(self._collection)
            latency_ms = (time.monotonic() - t0) * 1000

            vector_count: int = 0
            status_detail: str = "unknown"
            if info.vectors_count is not None:
                vector_count = info.vectors_count
            if info.status is not None:
                status_detail = str(info.status)

            return {
                "available": True,
                "latency_ms": round(latency_ms, 2),
                "collection": self._collection,
                "vector_count": vector_count,
                "status": status_detail,
                "error": None,
            }
        except UnexpectedResponse as exc:
            # Collection might not exist yet
            if exc.status_code == 404:
                return {
                    "available": True,
                    "latency_ms": None,
                    "collection": self._collection,
                    "vector_count": 0,
                    "status": "not_found",
                    "error": "Collection not yet initialised",
                }
            return {
                "available": False,
                "latency_ms": None,
                "collection": self._collection,
                "vector_count": 0,
                "error": str(exc),
            }
        except Exception as exc:
            logger.error("Qdrant health check failed: %s", exc)
            return {
                "available": False,
                "latency_ms": None,
                "collection": self._collection,
                "vector_count": 0,
                "error": str(exc),
            }
