"""
Retriever, Reranker, and Retrieval Pipeline for VisionRAG-X.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class Retriever:
    """
    Executes retrieval based on a routing decision from DynamicRouter.

    Delegates to HybridIndex for vector+lexical search and optionally
    augments results with VEKG concept search.
    """

    def __init__(
        self,
        hybrid_index: Any,
        vekg: Optional[Any] = None,
        settings: Optional[Any] = None,
    ):
        self.hybrid_index = hybrid_index
        self.vekg = vekg
        self.settings = settings

    async def retrieve(
        self,
        query: str,
        source_id: str,
        strategy: str,
        top_k: int = 10,
        modality_filter: Optional[str] = None,
        units_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve knowledge unit dicts ranked by relevance.

        Parameters
        ----------
        query : str
        source_id : str
        strategy : str  — value from RetrievalStrategy enum
        top_k : int
        modality_filter : str, optional  — e.g. 'formula', 'code'
        units_by_id : dict, optional  — unit_id -> unit dict for confidence lookup

        Returns
        -------
        List of result dicts from HybridIndex (includes unit_id, final_score, payload).
        """
        units_by_id = units_by_id or {}

        # Map strategy string to HybridIndex strategy param
        index_strategy_map = {
            'semantic_only': 'semantic',
            'lexical_only': 'lexical',
            'hybrid': 'hybrid',
            'formula_priority': 'hybrid',
            'code_priority': 'hybrid',
            'timestamp_aware': 'hybrid',
            'knowledge_graph': 'hybrid',
        }
        index_strategy = index_strategy_map.get(strategy, 'hybrid')

        results = await self.hybrid_index.search(
            query=query,
            source_id=source_id,
            top_k=top_k,
            strategy=index_strategy,
            units_by_id=units_by_id,
        )

        # Apply modality filter if requested
        if modality_filter and results:
            filtered = [
                r for r in results
                if r.get('payload', {}).get('modality') == modality_filter
            ]
            # Fall back to unfiltered if filter removes everything
            if filtered:
                results = filtered

        # Augment with VEKG concept search for knowledge_graph strategy
        if strategy == 'knowledge_graph' and self.vekg is not None:
            vekg_units = self.vekg.search_by_concept(query, threshold=0.4)
            vekg_ids = {u.id for u in vekg_units}
            # Add VEKG units not already in results
            existing_ids = {r['unit_id'] for r in results}
            for unit in vekg_units:
                if unit.id not in existing_ids and unit.source_id == source_id:
                    results.append({
                        'unit_id': unit.id,
                        'final_score': unit.confidence * 0.8,
                        'semantic_score': 0.0,
                        'lexical_score': 0.0,
                        'knowledge_confidence': unit.confidence,
                        'payload': {
                            'knowledge_unit_id': unit.id,
                            'concept': unit.concept,
                            'modality': unit.modality,
                            'confidence': unit.confidence,
                            'status': unit.status,
                            'content_preview': unit.content[:200],
                        },
                        'from_vekg': True,
                    })

        # Sort by final score
        results.sort(key=lambda r: r.get('final_score', 0.0), reverse=True)
        return results[:top_k]


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------

class Reranker:
    """
    Post-retrieval reranker.

    First version: score-fusion reranking with status-based adjustments.
    Interface supports cross-encoder model replacement in future work.

    Status adjustments:
    - verified:  +10% boost
    - active:    no change
    - disputed:  -15% penalty
    - superseded: -20% penalty
    """

    STATUS_ADJUSTMENTS = {
        'verified': 1.10,
        'active': 1.00,
        'disputed': 0.85,
        'superseded': 0.80,
    }

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        units_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Rerank retrieved results.

        Parameters
        ----------
        query : str
        results : list of result dicts from Retriever
        units_by_id : dict, optional

        Returns
        -------
        Sorted list of (result_dict, final_score) tuples.
        """
        units_by_id = units_by_id or {}
        ranked: List[Tuple[Dict[str, Any], float]] = []

        for result in results:
            base_score = float(result.get('final_score', 0.0))
            unit = units_by_id.get(result['unit_id'], {})
            status = unit.get('status') or result.get('payload', {}).get('status', 'active')
            adjustment = self.STATUS_ADJUSTMENTS.get(status, 1.0)
            final = min(1.0, base_score * adjustment)
            ranked.append((result, final))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def select_evidence(
        self,
        ranked: List[Tuple[Dict[str, Any], float]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Select top_k results after reranking."""
        return [r for r, _ in ranked[:top_k]]

    # Interface for future cross-encoder
    async def rerank_with_model(
        self,
        query: str,
        results: List[Dict[str, Any]],
    ) -> List[Tuple[Dict[str, Any], float]]:
        raise NotImplementedError(
            'Cross-encoder reranking not yet implemented. '
            'Implement this to replace score-fusion reranking.'
        )


# ---------------------------------------------------------------------------
# Retrieval Pipeline
# ---------------------------------------------------------------------------

class RetrievalPipeline:
    """
    Orchestrates the full retrieval flow:
    query → classify → route → retrieve → rerank → select evidence
    """

    def __init__(
        self,
        router: Any,
        retriever: Retriever,
        reranker: Reranker,
        provenance: Any,
        settings: Optional[Any] = None,
    ):
        self.router = router
        self.retriever = retriever
        self.reranker = reranker
        self.provenance = provenance
        self.settings = settings

    async def run(
        self,
        query: str,
        source_id: str,
        source_type: str,
        top_k: int = 5,
        include_conflicts: bool = True,
        conflicts: Optional[List[Dict[str, Any]]] = None,
        units_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the full retrieval pipeline.

        Returns
        -------
        dict:
            evidence         : List[dict] — selected evidence items
            query_type       : str
            strategy_used    : str
            routing_explanation : str
            conflicts        : List[dict] — relevant conflicts (if any)
            latency_ms       : float
        """
        t0 = time.perf_counter()
        units_by_id = units_by_id or {}
        conflicts = conflicts or []

        # 1. Route
        routing = self.router.route(query, source_type)
        strategy = routing['strategy']
        top_k_eff = routing.get('top_k_override') or top_k
        modality_filter = routing.get('modality_filter')

        logger.info(
            'Query routed: type=%s strategy=%s top_k=%d',
            routing['query_type'], strategy, top_k_eff,
        )

        # 2. Retrieve
        results = await self.retriever.retrieve(
            query=query,
            source_id=source_id,
            strategy=strategy,
            top_k=top_k_eff * 2,  # over-retrieve then rerank
            modality_filter=modality_filter,
            units_by_id=units_by_id,
        )

        # 3. Rerank
        ranked = self.reranker.rerank(query, results, units_by_id)

        # 4. Select evidence
        selected = self.reranker.select_evidence(ranked, top_k=top_k)

        # 5. Build provenance items
        # Convert selected results to unit-like dicts for provenance
        evidence_units = []
        for r in selected:
            payload = r.get('payload', {})
            unit = units_by_id.get(r['unit_id'], {})
            merged = {**payload, **unit, 'id': r['unit_id']}
            evidence_units.append(merged)

        provenance_items = self.provenance.build_provenance(query, evidence_units, query)

        # 6. Filter conflicts relevant to this window (approximate)
        relevant_conflicts = conflicts if include_conflicts else []

        latency_ms = (time.perf_counter() - t0) * 1000

        return {
            'evidence': provenance_items,
            'query_type': routing['query_type'],
            'strategy_used': strategy,
            'routing_explanation': routing['explanation'],
            'conflicts': relevant_conflicts,
            'latency_ms': round(latency_ms, 2),
        }
