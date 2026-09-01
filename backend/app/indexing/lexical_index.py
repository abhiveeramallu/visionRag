"""
BM25 lexical index for VisionRAG-X.
In-memory per-source index using rank-bm25.
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Very small stop-word list — keep it minimal to preserve technical terms
_STOP_WORDS = {
    'a', 'an', 'the', 'is', 'it', 'in', 'on', 'at', 'to', 'for',
    'of', 'and', 'or', 'but', 'not', 'with', 'as', 'by', 'from',
    'this', 'that', 'are', 'was', 'were', 'be', 'been', 'has', 'have',
    'had', 'do', 'does', 'did', 'will', 'would', 'can', 'could',
}


def _tokenize(text: str) -> List[str]:
    """Lowercase, split on non-word chars, remove stop words and empty tokens."""
    tokens = re.split(r'\W+', text.lower())
    return [t for t in tokens if t and t not in _STOP_WORDS and len(t) > 1]


class LexicalIndex:
    """
    BM25-based lexical search index.

    Backed by rank_bm25.BM25Okapi. Held in memory for the prototype.
    The index is rebuilt from scratch on any add/remove operation.
    """

    def __init__(self):
        self._units: List[Dict[str, Any]] = []   # ordered list of unit dicts
        self._bm25 = None                         # BM25Okapi instance
        self._available: Optional[bool] = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def _check_availability(self) -> bool:
        if self._available is None:
            try:
                from rank_bm25 import BM25Okapi  # noqa: F401
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        """Rebuild the BM25 index from self._units."""
        if not self._check_availability():
            logger.warning('rank_bm25 not available — lexical search disabled')
            self._bm25 = None
            return
        if not self._units:
            self._bm25 = None
            return
        from rank_bm25 import BM25Okapi
        corpus = [_tokenize(u.get('content', '')) or ['text'] for u in self._units]
        self._bm25 = BM25Okapi(corpus)

    def build_index(self, units: List[Dict[str, Any]]) -> None:
        """Build index from scratch with the given unit list."""
        self._units = list(units)
        self._rebuild()
        logger.info('Lexical index built with %d units', len(self._units))

    def add_units(self, units: List[Dict[str, Any]]) -> None:
        """Incrementally add units and rebuild the index."""
        existing_ids = {u.get('id') for u in self._units}
        new_units = [u for u in units if u.get('id') not in existing_ids]
        self._units.extend(new_units)
        self._rebuild()
        logger.debug('Added %d units to lexical index (total: %d)', len(new_units), len(self._units))

    def remove_source(self, source_id: str) -> None:
        """Remove all units belonging to a source and rebuild."""
        before = len(self._units)
        self._units = [u for u in self._units if u.get('source_id') != source_id]
        self._rebuild()
        logger.info('Removed %d units for source %s from lexical index', before - len(self._units), source_id)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        source_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        BM25 search over indexed units.

        Parameters
        ----------
        query : str
            User query string.
        source_id : str, optional
            If provided, restrict results to this source.
        top_k : int
            Maximum results to return.

        Returns
        -------
        List of dicts: {unit_id, score}.
        """
        if self._bm25 is None or not self._units:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # Build (index, score) pairs filtered by source_id
        candidates = [
            (i, float(scores[i]))
            for i, unit in enumerate(self._units)
            if scores[i] > 0 and (source_id is None or unit.get('source_id') == source_id)
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                'unit_id': self._units[i].get('id', ''),
                'score': score,
            }
            for i, score in candidates[:top_k]
        ]

    def __len__(self) -> int:
        return len(self._units)
