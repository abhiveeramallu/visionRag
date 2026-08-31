"""
Dynamic retrieval router for VisionRAG-X.

EXPERIMENTAL: Uses transparent, hand-crafted heuristic rules.
Interface supports replacing with a learned classifier in future work.
"""
import logging
import re
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    FORMULA = 'formula'
    TIMESTAMP = 'timestamp'
    DEFINITION = 'definition'
    CODE = 'code'
    CONCEPTUAL = 'conceptual'
    FACTUAL = 'factual'
    GENERAL = 'general'


class RetrievalStrategy(str, Enum):
    SEMANTIC_ONLY = 'semantic_only'
    LEXICAL_ONLY = 'lexical_only'
    HYBRID = 'hybrid'
    FORMULA_PRIORITY = 'formula_priority'
    TIMESTAMP_AWARE = 'timestamp_aware'
    CODE_PRIORITY = 'code_priority'
    KNOWLEDGE_GRAPH = 'knowledge_graph'


class DynamicRouter:
    """
    Rule-based query classification and retrieval strategy selection.

    EXPERIMENTAL: All rules are deterministic, keyword-based heuristics.
    They are transparent and auditable but have NOT been evaluated against
    a labelled query dataset.

    Interface is designed so that a learned router can replace classify_query()
    or the entire route() method via implement route_with_model().
    """

    FORMULA_INDICATORS = [
        'formula', 'equation', 'complexity', r'o\(n', 'derivative', 'integral',
        'theorem', 'proof', 'calculate', 'compute', 'expression', 'polynomial',
        'logarithm', 'exponent', 'matrix', 'determinant', 'eigenvalue', 'gradient',
        'divergence', 'curl', r'big.o', 'asymptotic', 'recurrence', 'summation',
    ]
    TIMESTAMP_INDICATORS = [
        'when', 'where did', 'at what time', 'which part', 'timestamp',
        'which minute', 'which section', 'mentioned', 'said', 'explain again',
        'what time', 'how far in', 'minute', 'second', 'beginning', 'end of',
    ]
    CODE_INDICATORS = [
        'code', 'function', 'algorithm', 'implementation', 'program',
        'syntax', 'method', 'class', 'variable', 'loop', 'recursive',
        'pseudocode', 'snippet', 'script', 'library', 'import', 'compile',
        'debug', 'error', 'exception', 'lambda', 'callback', 'api',
    ]
    DEFINITION_INDICATORS = [
        'what is', 'define', 'definition of', 'what does', 'meaning of',
        'explain', 'describe', 'what are', 'how does', 'who is',
        'difference between', 'compare', 'contrast', 'distinguish',
    ]
    CONCEPTUAL_INDICATORS = [
        'why', 'how', 'intuition', 'understand', 'concept', 'idea',
        'principle', 'theory', 'motivation', 'reason', 'implication',
        'consequence', 'effect', 'relationship', 'connection', 'analogy',
    ]
    FACTUAL_INDICATORS = [
        'what year', 'who invented', 'when was', 'how many', 'what number',
        'first', 'last', 'which', 'example of', 'list', 'name',
    ]

    def __init__(self):
        # Pre-compile patterns for performance
        self._formula_re = re.compile(
            '|'.join(self.FORMULA_INDICATORS), re.IGNORECASE
        )
        self._timestamp_re = re.compile(
            '|'.join(re.escape(p) if ' ' not in p else p for p in self.TIMESTAMP_INDICATORS),
            re.IGNORECASE,
        )
        self._code_re = re.compile('|'.join(self.CODE_INDICATORS), re.IGNORECASE)
        self._definition_re = re.compile(
            '|'.join(re.escape(p) for p in self.DEFINITION_INDICATORS), re.IGNORECASE
        )
        self._conceptual_re = re.compile('|'.join(self.CONCEPTUAL_INDICATORS), re.IGNORECASE)
        self._factual_re = re.compile(
            '|'.join(re.escape(p) for p in self.FACTUAL_INDICATORS), re.IGNORECASE
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify_query(self, query: str) -> QueryType:
        """
        Classify a user query into a QueryType using heuristic rules.

        Rules are evaluated in priority order: formula > timestamp > code >
        definition > conceptual > factual > general.
        """
        q = query.strip()

        if self._formula_re.search(q):
            return QueryType.FORMULA
        if self._timestamp_re.search(q):
            return QueryType.TIMESTAMP
        if self._code_re.search(q):
            return QueryType.CODE
        if self._definition_re.search(q):
            return QueryType.DEFINITION
        if self._conceptual_re.search(q):
            return QueryType.CONCEPTUAL
        if self._factual_re.search(q):
            return QueryType.FACTUAL
        return QueryType.GENERAL

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    def get_strategy(
        self,
        query_type: QueryType,
        source_type: str,
    ) -> RetrievalStrategy:
        """Map a query type + source type to a retrieval strategy."""
        is_video = source_type in ('youtube', 'video', 'audio')

        strategy_map = {
            QueryType.FORMULA: RetrievalStrategy.FORMULA_PRIORITY,
            QueryType.TIMESTAMP: (
                RetrievalStrategy.TIMESTAMP_AWARE if is_video
                else RetrievalStrategy.HYBRID
            ),
            QueryType.CODE: RetrievalStrategy.CODE_PRIORITY,
            QueryType.DEFINITION: RetrievalStrategy.SEMANTIC_ONLY,
            QueryType.CONCEPTUAL: RetrievalStrategy.KNOWLEDGE_GRAPH,
            QueryType.FACTUAL: RetrievalStrategy.HYBRID,
            QueryType.GENERAL: RetrievalStrategy.HYBRID,
        }
        return strategy_map.get(query_type, RetrievalStrategy.HYBRID)

    # ------------------------------------------------------------------
    # Public routing
    # ------------------------------------------------------------------

    def route(self, query: str, source_type: str) -> Dict[str, Any]:
        """
        Classify the query and return a routing decision.

        Returns
        -------
        dict with keys:
        - query_type (str)
        - strategy (str)
        - explanation (str) — human-readable rationale
        - top_k_override (int or None)
        - modality_filter (str or None) — e.g. 'formula', 'code'
        """
        query_type = self.classify_query(query)
        strategy = self.get_strategy(query_type, source_type)

        explanations = {
            QueryType.FORMULA: 'Query contains formula/complexity indicators → formula-priority retrieval',
            QueryType.TIMESTAMP: 'Query asks about location/time → timestamp-aware retrieval',
            QueryType.CODE: 'Query is about code/algorithms → code-priority retrieval',
            QueryType.DEFINITION: 'Query is a definition request → semantic-only retrieval',
            QueryType.CONCEPTUAL: 'Query is conceptual → knowledge-graph-augmented hybrid retrieval',
            QueryType.FACTUAL: 'Query is factual → hybrid retrieval',
            QueryType.GENERAL: 'General query → hybrid retrieval',
        }

        modality_filters = {
            QueryType.FORMULA: 'formula',
            QueryType.CODE: 'code',
        }

        top_k_overrides = {
            QueryType.FORMULA: 8,
            QueryType.CODE: 8,
            QueryType.TIMESTAMP: 10,
        }

        return {
            'query_type': query_type.value,
            'strategy': strategy.value,
            'explanation': explanations.get(query_type, 'General hybrid retrieval'),
            'top_k_override': top_k_overrides.get(query_type),
            'modality_filter': modality_filters.get(query_type),
        }

    # ------------------------------------------------------------------
    # Interface for future learned router
    # ------------------------------------------------------------------

    async def route_with_model(self, query: str, source_type: str) -> Dict[str, Any]:
        """
        Learned routing model — NOT YET IMPLEMENTED.

        Implement this to replace rule-based routing with a trained classifier.
        Expected interface: same return dict as route().
        """
        raise NotImplementedError(
            'Learned routing model not yet implemented. '
            'To add it: train a classifier on query–strategy pairs and '
            'implement this method. The rule-based route() remains as fallback.'
        )
