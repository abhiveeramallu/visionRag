"""
Hybrid index combining semantic (vector) and lexical (BM25) retrieval.

EXPERIMENTAL: Score fusion formula and weights have not been optimised
experimentally. Alpha/beta/gamma are configurable for ablation studies.
"""
import logging
from typing import Any, Dict, List, Optional

from app.indexing.vector_index import VectorIndex
from app.indexing.lexical_index import LexicalIndex

logger = logging.getLogger(__name__)


class HybridIndex:
    """
    Fuses semantic and lexical retrieval scores.

    EXPERIMENTAL fusion formula:
        final_score = α × semantic_score
                    + β × lexical_score
                    + γ × knowledge_confidence

    where α + β + γ = 1 (normalised internally).
    Default values: α=0.6, β=0.3, γ=0.1.

    These weights have NOT been optimised on a held-out dataset.
    Use the ablation config to experiment with different values.
    """

    def __init__(
        self,
        vector_index: VectorIndex,
        lexical_index: LexicalIndex,
        alpha: float = 0.6,
        beta: float = 0.3,
        gamma: float = 0.1,
    ):
        self.vector_index = vector_index
        self.lexical_index = lexical_index
        # Normalise weights
        total = alpha + beta + gamma
        self.alpha = alpha / total
        self.beta = beta / total
        self.gamma = gamma / total
        logger.debug(
            'HybridIndex weights — α(semantic)=%.2f β(lexical)=%.2f γ(confidence)=%.2f',
            self.alpha, self.beta, self.gamma,
        )

    # ------------------------------------------------------------------
    # Score helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_scores(scores: List[float]) -> List[float]:
        """Min-max normalisation to [0, 1]. Returns zeros for empty/uniform input."""
        if not scores:
            return []
        mn, mx = min(scores), max(scores)
        if mx == mn:
            return [0.5] * len(scores)
        return [(s - mn) / (mx - mn) for s in scores]

    async def _fuse_scores(
        self,
        semantic_results: List[Dict[str, Any]],
        lexical_results: List[Dict[str, Any]],
        units_by_id: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Combine semantic and lexical scores using weighted fusion."""
        # Build lookup maps
        sem_map: Dict[str, float] = {r['unit_id']: r['score'] for r in semantic_results}
        lex_map: Dict[str, float] = {r['unit_id']: r['score'] for r in lexical_results}

        all_ids = list(set(sem_map) | set(lex_map))
        if not all_ids:
            return []

        # Collect raw scores
        sem_raw = [sem_map.get(uid, 0.0) for uid in all_ids]
        lex_raw = [lex_map.get(uid, 0.0) for uid in all_ids]

        # Normalise
        sem_norm = self._normalize_scores(sem_raw)
        lex_norm = self._normalize_scores(lex_raw)

        fused: List[Dict[str, Any]] = []
        for i, uid in enumerate(all_ids):
            unit = units_by_id.get(uid, {})
            confidence = float(unit.get('confidence', 0.5))
            s_score = sem_norm[i]
            l_score = lex_norm[i]
            final = self.alpha * s_score + self.beta * l_score + self.gamma * confidence

            # Collect payload from whichever index found it
            sem_hit = next((r for r in semantic_results if r['unit_id'] == uid), None)
            payload = sem_hit.get('payload', {}) if sem_hit else {}

            fused.append({
                'unit_id': uid,
                'final_score': round(final, 4),
                'semantic_score': round(s_score, 4),
                'lexical_score': round(l_score, 4),
                'knowledge_confidence': round(confidence, 4),
                'payload': payload,
            })

        fused.sort(key=lambda x: x['final_score'], reverse=True)
        return fused

    # ------------------------------------------------------------------
    # Public search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        source_id: Optional[str] = None,
        top_k: int = 10,
        strategy: str = 'hybrid',
        units_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search over the combined index.

        Parameters
        ----------
        query : str
        source_id : str, optional
        top_k : int
        strategy : str
            'semantic' — vector search only
            'lexical'  — BM25 search only
            'hybrid'   — weighted fusion (default)
        units_by_id : dict, optional
            Mapping of unit_id -> unit dict for confidence lookup.
            Required for γ-weighting; if omitted, γ term is skipped.

        Returns
        -------
        List of result dicts with unit_id, final_score, etc.
        """
        units_by_id = units_by_id or {}

        if strategy == 'semantic':
            results = await self.vector_index.search(query, source_id, top_k)
            return [
                {
                    'unit_id': r['unit_id'],
                    'final_score': r['score'],
                    'semantic_score': r['score'],
                    'lexical_score': 0.0,
                    'knowledge_confidence': units_by_id.get(r['unit_id'], {}).get('confidence', 0.5),
                    'payload': r.get('payload', {}),
                }
                for r in results
            ]

        if strategy == 'lexical':
            results = self.lexical_index.search(query, source_id, top_k)
            norm_scores = self._normalize_scores([r['score'] for r in results])
            return [
                {
                    'unit_id': r['unit_id'],
                    'final_score': norm_scores[i],
                    'semantic_score': 0.0,
                    'lexical_score': norm_scores[i],
                    'knowledge_confidence': units_by_id.get(r['unit_id'], {}).get('confidence', 0.5),
                    'payload': {},
                }
                for i, r in enumerate(results)
            ]

        # Default: hybrid fusion
        semantic_results = await self.vector_index.search(query, source_id, top_k * 2)
        lexical_results = self.lexical_index.search(query, source_id, top_k * 2)

        fused = await self._fuse_scores(semantic_results, lexical_results, units_by_id)
        return fused[:top_k]
