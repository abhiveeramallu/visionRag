"""
Retriever, Reranker, and Retrieval Pipeline for VisionRAG-X.
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

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

        # Apply modality priority/boost if requested (soft priority instead of hard filtering)
        if modality_filter and results:
            for r in results:
                if r.get('payload', {}).get('modality') == modality_filter:
                    r['final_score'] = min(1.0, r.get('final_score', 0.0) * 1.30)
            results.sort(key=lambda r: r.get('final_score', 0.0), reverse=True)

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

    def filter_relevant_conflicts(
        self,
        conflicts: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        query: str,
        max_conflicts: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Filter and rank conflicts relevant to the current query and retrieved evidence.

        Employs an evidence-aware matching policy:
        1. Symbol & Complexity Preservation:
           Preserves short symbols (e.g. 'v', 'a', 'm'), formulas, and complexity
           notation (e.g. 'O(n)' vs 'O(n^2)') without discarding short tokens.
        2. Lineage & Concept Linking:
           Matches conflicts directly linked by entity concept, unit IDs, or
           version lineage to retrieved evidence.
        3. Distant Correction Retrieval:
           Allows retrieval of conflicts even if the correction occurred far apart
           in time (e.g. 40 minutes later) or on different slides, as long as
           topical or claim relevance connects them.
        4. Temporal Proximity Ranking Signal:
           Uses temporal and slide proximity as ranking signals rather than an
           unconditional exclusion rule for known linked conflicts.
        5. Bounded Output:
           Sorts relevant conflicts by match score and bounds to top `max_conflicts`.
        """
        if not conflicts or not evidence_items:
            return []

        CONFLICT_STOPWORDS = {
            'a', 'an', 'the', 'in', 'on', 'at', 'of', 'to', 'for', 'with', 'by', 'as',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'from', 'this', 'that', 'these', 'those', 'it', 'its',
            'they', 'them', 'their', 'we', 'us', 'our', 'you', 'your', 'and', 'or', 'not',
            'slide', 'spoken', 'text', 'audio', 'ocr', 'asr', 'unit', 'source', 'statement',
            'authoritative', 'incorrect', 'omission', 'earlier', 'mistake', 'without',
            'factor', 'stated', 'instructor', 'discrepancy', 'disagreement', 'contradiction',
            'notice', 'later', 'what', 'which', 'where', 'when', 'how', 'formula', 'algorithm',
            'explain', 'show', 'tell', 'state', 'value', 'data', 'structure', 'rule', 'definition',
            'time', 'complexity', 'space', 'relation',
            'layer', 'layers', 'protocol', 'protocols', 'model', 'packet', 'packets',
            'string', 'strings', 'tree', 'trees', 'loop', 'loops', 'table', 'tables'
        }

        def _extract_tokens_and_symbols(text: str) -> Set[str]:
            if not text:
                return set()
            text_clean = text.lower()
            # Complexity expressions: o(n), o(n^2), o(n log n), o(1), o(2^n)
            complexities = set(re.findall(r'o\([^\)]+\)', text_clean))
            # Variable names and alphanumeric symbols
            raw_words = set(re.findall(r'\b[a-z0-9_]+\b', text_clean))
            formula_tokens = set(re.findall(r'[a-z0-9_\^²³]+', text_clean))
            meaningful_words = {w for w in raw_words if len(w) > 1 or w in {'m', 'v', 'c', 'e'}}

            all_tokens = (complexities | meaningful_words | formula_tokens) - CONFLICT_STOPWORDS
            normalized = set()
            for t in all_tokens:
                # Omit isolated single digits like '2', '3', '7' from claim tokens
                if len(t) == 1 and t.isdigit():
                    continue
                normalized.add(t)
                if '²' in t:
                    normalized.add(t.replace('²', '^2'))
                if '^2' in t:
                    normalized.add(t.replace('^2', '²'))
            return normalized

        ev_timestamps = [
            e['timestamp_start'] for e in evidence_items
            if e.get('timestamp_start') is not None
        ]
        ev_pages = {
            e.get('page') or e.get('slide') for e in evidence_items
            if e.get('page') is not None or e.get('slide') is not None
        }
        ev_concepts = {
            str(e.get('concept', '')).lower() for e in evidence_items if e.get('concept')
        }
        ev_unit_ids = {
            str(e.get('knowledge_unit_id') or e.get('id') or '')
            for e in evidence_items
            if e.get('knowledge_unit_id') or e.get('id')
        }
        ev_prev_ids = {
            str(e.get('previous_version_id', '')) for e in evidence_items if e.get('previous_version_id')
        }
        ev_text = ' '.join(
            str(e.get('text') or e.get('content') or '') for e in evidence_items
        )

        query_tokens = _extract_tokens_and_symbols(query)
        evidence_tokens = _extract_tokens_and_symbols(ev_text)

        scored_conflicts = []

        for c in conflicts:
            c_ts = c.get('timestamp')
            c_page = c.get('page')
            c_concept = str(c.get('concept', '')).lower()
            c_concept_tokens = _extract_tokens_and_symbols(c_concept)
            c_claims_raw = ' '.join(str(cl) for cl in c.get('claims', []))
            c_claim_tokens = _extract_tokens_and_symbols(c_claims_raw)
            c_unit_ids = {str(uid) for uid in c.get('unit_ids', []) if uid}

            # 1. Lineage & ID linkage
            has_id_link = bool(c_unit_ids and (c_unit_ids & (ev_unit_ids | ev_prev_ids)))
            ev_concept_tokens = _extract_tokens_and_symbols(' '.join(ev_concepts))
            has_ev_concept_link = len(c_concept_tokens & ev_concept_tokens) >= 1
            has_ev_claim_link = bool(c_claim_tokens & evidence_tokens)

            if c_concept_tokens:
                evidence_linked = has_id_link or (has_ev_concept_link and has_ev_claim_link)
            else:
                evidence_linked = has_id_link or has_ev_claim_link

            # 2. Query topicality: question mentions topic concept or disputed claims
            query_concept_overlap = c_concept_tokens & query_tokens
            query_claim_overlap = c_claim_tokens & query_tokens
            query_topical = len(query_concept_overlap) >= 1 or bool(query_claim_overlap)

            # A conflict is relevant to this specific answer iff:
            # - If linked by unit ID: relevant unless the conflict specifies an explicit topic concept
            #   and the query explicitly targets a different, non-overlapping subject.
            # - Otherwise: requires both evidence topic/claim linkage and query topicality.
            is_relevant = False
            if has_id_link:
                if c_concept_tokens:
                    if query_tokens and not query_topical:
                        is_relevant = False
                    else:
                        is_relevant = True
                else:
                    is_relevant = True
            elif evidence_linked and query_topical:
                is_relevant = True

            if is_relevant:
                score = 5.0 if has_id_link else 3.0
                score += 2.0 * len(query_concept_overlap | query_claim_overlap)

                # Page match boost
                if c_page is not None and ev_pages and c_page in ev_pages:
                    score += 1.5

                # Temporal proximity ranking signal (boost only)
                if c_ts is not None and ev_timestamps:
                    min_delta = min(abs(c_ts - ts) for ts in ev_timestamps)
                    score += 2.0 / (1.0 + min_delta / 30.0)

                scored_conflicts.append((score, c))

        # Sort descending by relevance score and bound
        scored_conflicts.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_conflicts[:max_conflicts]]

    def check_evidence_sufficiency(
        self,
        query: str,
        evidence_units: List[Dict[str, Any]],
        max_score: float = 1.0,
    ) -> Tuple[bool, str]:
        """
        Subject-aware evidence sufficiency gate.
        Determines whether the retrieved evidence grounds the query's specific subjects.
        Returns (is_sufficient: bool, reason: str).
        """
        if not evidence_units:
            return False, "No evidence retrieved."

        STOPWORDS = {
            'a', 'an', 'the', 'in', 'on', 'at', 'of', 'to', 'for', 'with', 'by', 'as',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'from', 'this', 'that', 'these', 'those', 'it', 'its',
            'they', 'them', 'their', 'we', 'us', 'our', 'you', 'your', 'and', 'or', 'not',
            'but', 'if', 'then', 'else', 'me', 'my'
        }
        GENERIC_QUERY_TERMS = {
            'what', 'which', 'where', 'when', 'show', 'explain', 'tell', 'how',
            'time', 'complexity', 'algorithm', 'formula', 'data', 'structure', 'state',
            'value', 'used', 'using', 'calculate', 'function', 'case', 'equation', 'rule'
        }
        q_tokens = re.findall(r'\b[a-zA-Z0-9_\^²³]{2,}\b', query.lower())
        content_tokens = [t for t in q_tokens if t not in STOPWORDS]
        subject_tokens = [t for t in content_tokens if t not in GENERIC_QUERY_TERMS]

        ev_text = ' '.join(
            (str(e.get('concept', '')) + ' ' + str(e.get('text') or e.get('content') or '')).lower()
            for e in evidence_units
        )
        overlap_subj = [t for t in subject_tokens if t in ev_text]

        if max_score < 0.20:
            return False, f"Relevance score {max_score:.2f} below minimum sufficiency threshold (0.20)"

        if len(subject_tokens) > 0 and len(overlap_subj) == 0:
            return False, f"Distinctive subject terms {subject_tokens} not grounded in retrieved evidence"

        return True, "Evidence sufficient"

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
            abstain          : bool — whether system abstains due to insufficient evidence
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

        # 5. Build raw evidence units
        raw_evidence_units = []
        for r in selected:
            payload = r.get('payload', {})
            unit = units_by_id.get(r['unit_id'], {})
            merged = {**payload, **unit, 'id': r['unit_id']}
            raw_evidence_units.append(merged)

        # 6. VEKG correction traversal: substitute superseded units with active corrections
        evidence_units = []
        vekg_instance = getattr(self.retriever, 'vekg', None)
        for unit in raw_evidence_units:
            if unit.get('status') == 'superseded' and vekg_instance is not None:
                lineage = vekg_instance.get_lineage(unit.get('id', ''))
                active_u = lineage[0] if lineage else None
                if active_u:
                    active_dict = active_u.__dict__ if hasattr(active_u, '__dict__') else dict(active_u)
                    evidence_units.append(active_dict)
                else:
                    newer_id = next((uid for uid, u in units_by_id.items() if u.get('previous_version_id') == unit.get('id')), None)
                    if newer_id and newer_id in units_by_id:
                        evidence_units.append({**units_by_id[newer_id], 'id': newer_id})
                    else:
                        evidence_units.append(unit)
            else:
                evidence_units.append(unit)

        # 7. Grounded evidence sufficiency & abstention gate
        max_score = ranked[0][1] if ranked else 0.0
        is_sufficient, reason = self.check_evidence_sufficiency(query, evidence_units, max_score)
        should_abstain = not is_sufficient

        if should_abstain:
            logger.info("Abstention triggered for query '%s': %s", query, reason)
            provenance_items = []
            relevant_conflicts = []
        else:
            provenance_items = self.provenance.build_provenance(query, evidence_units, query)
            # 8. Filter conflicts relevant to this window
            relevant_conflicts = (
                self.filter_relevant_conflicts(conflicts, evidence_units, query)
                if include_conflicts else []
            )

        latency_ms = (time.perf_counter() - t0) * 1000

        return {
            'evidence': provenance_items,
            'query_type': routing['query_type'],
            'strategy_used': strategy,
            'routing_explanation': routing['explanation'],
            'conflicts': relevant_conflicts,
            'abstain': should_abstain,
            'abstention_reason': reason if should_abstain else None,
            'latency_ms': round(latency_ms, 2),
        }
