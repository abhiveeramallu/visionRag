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

# Process-wide singleton for embedded local Qdrant client to avoid portalocker file-lock contention
_SHARED_LOCAL_CLIENT: Optional[AsyncQdrantClient] = None

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
        self._using_local = False

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

    async def _ensure_client(self) -> None:
        """
        Verify the Qdrant client connection.
        If the remote Qdrant server is unreachable (e.g. running locally without Docker),
        automatically fall back to embedded on-disk vector storage.
        """
        global _SHARED_LOCAL_CLIENT

        if self._using_local:
            return

        if _SHARED_LOCAL_CLIENT is not None:
            self.client = _SHARED_LOCAL_CLIENT
            self._using_local = True
            return

        try:
            await self.client.get_collections()
        except Exception as exc:
            from pathlib import Path
            local_dir = Path(self._settings.processed_dir) / "qdrant_storage"
            local_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(
                "Remote Qdrant at %s unreachable (%s). Falling back to embedded local storage at %s.",
                self._settings.qdrant_url,
                exc,
                local_dir,
            )
            if _SHARED_LOCAL_CLIENT is None:
                try:
                    _SHARED_LOCAL_CLIENT = AsyncQdrantClient(path=str(local_dir))
                except Exception as lock_err:
                    logger.warning(
                        "Qdrant storage folder %s locked or unavailable (%s); using in-memory vector store",
                        local_dir,
                        lock_err,
                    )
                    _SHARED_LOCAL_CLIENT = AsyncQdrantClient(location=":memory:")
            self.client = _SHARED_LOCAL_CLIENT
            self._using_local = True

            # Ensure collection exists on local embedded instance
            cols = [c.name for c in (await self.client.get_collections()).collections]
            if self._collection not in cols:
                await self.client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=self._vector_size,
                        distance=Distance.COSINE,
                    ),
                )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init_collection(self) -> None:
        """
        Ensure the target collection exists.
        Creates it with COSINE distance if absent; skips silently if present.
        """
        await self._ensure_client()
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
        """
        if not points:
            return
        await self._ensure_client()
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
        """
        await self._ensure_client()
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
        """
        await self._ensure_client()
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
