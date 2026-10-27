"""
Retriever, Reranker, and Retrieval Pipeline for VisionRAG-X.
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def _extract_temporal_targets(query: str) -> Dict[str, Any]:
    """
    Extract timestamps (MM:SS, HH:MM:SS, minutes, seconds), ranges, or page/slide numbers from query.
    """
    res = {'target_sec': None, 'start_sec': None, 'end_sec': None, 'page': None, 'slide': None}
    q = query.lower()

    # 1. MM:SS or HH:MM:SS (e.g. 05:15 or 1:30:00)
    time_matches = re.findall(r'\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b', q)
    if time_matches:
        parts = time_matches[0]
        if parts[0]:
            res['target_sec'] = float(int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
        else:
            res['target_sec'] = float(int(parts[1]) * 60 + int(parts[2]))
        if len(time_matches) > 1:
            p2 = time_matches[1]
            sec2 = float(int(p2[0] or 0) * 3600 + int(p2[1]) * 60 + int(p2[2]))
            res['start_sec'] = min(res['target_sec'], sec2)
            res['end_sec'] = max(res['target_sec'], sec2)

    # 2. "minute X" or "X minutes" or "X min"
    if res['target_sec'] is None:
        min_m = re.search(r'\b(?:at|around|in)?\s*(?:minute\s*(\d+)|(\d+)\s*(?:minute|minutes|min))\b', q)
        if min_m:
            mins = int(min_m.group(1) or min_m.group(2))
            res['target_sec'] = float(mins * 60)

    # 3. "X seconds" or "X sec" or "X s"
    if res['target_sec'] is None:
        sec_m = re.search(r'\b(?:at|around|in)?\s*(\d+)\s*(?:seconds|second|sec|s)\b', q)
        if sec_m:
            res['target_sec'] = float(sec_m.group(1))

    # 4. Page or Slide references (for documents)
    page_m = re.search(r'\bpage\s*(\d+)\b', q)
    if page_m:
        res['page'] = int(page_m.group(1))

    slide_m = re.search(r'\bslide\s*(\d+)\b', q)
    if slide_m:
        res['slide'] = int(slide_m.group(1))

    return res


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
        source_id: Optional[str],
        strategy: str,
        top_k: int = 10,
        modality_filter: Optional[str] = None,
        units_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
        timestamp_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve knowledge unit dicts ranked by relevance.
        Supports Semantic, Keyword (BM25), Knowledge Graph (VEKG), Timestamp, and Hybrid strategies.
        """
        units_by_id = units_by_id or {}
        is_all_sources = not source_id or source_id.lower() in ('all', 'all_sources', '*')
        target_source_id = None if is_all_sources else source_id

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
            source_id=target_source_id,
            top_k=top_k,
            strategy=index_strategy,
            units_by_id=units_by_id,
        )

        # 1. Modality priority or hard filter
        if modality_filter and results:
            for r in results:
                unit_mod = (
                    units_by_id.get(r.get('unit_id'), {}).get('modality')
                    or r.get('payload', {}).get('modality')
                )
                if unit_mod == modality_filter:
                    r['final_score'] = min(1.0, r.get('final_score', 0.0) + 0.40)
                else:
                    r['final_score'] = r.get('final_score', 0.0) * 0.75
            results.sort(key=lambda r: r.get('final_score', 0.0), reverse=True)

        # 2. Timestamp & Temporal Location Matching
        temporal_info = _extract_temporal_targets(query)
        if timestamp_filter:
            if 'target_sec' in timestamp_filter and timestamp_filter['target_sec'] is not None:
                temporal_info['target_sec'] = float(timestamp_filter['target_sec'])
            if 'start_sec' in timestamp_filter and timestamp_filter['start_sec'] is not None:
                temporal_info['start_sec'] = float(timestamp_filter['start_sec'])
            if 'end_sec' in timestamp_filter and timestamp_filter['end_sec'] is not None:
                temporal_info['end_sec'] = float(timestamp_filter['end_sec'])
            if 'page' in timestamp_filter and timestamp_filter['page'] is not None:
                temporal_info['page'] = int(timestamp_filter['page'])
            if 'slide' in timestamp_filter and timestamp_filter['slide'] is not None:
                temporal_info['slide'] = int(timestamp_filter['slide'])
        is_timestamp_query = (
            strategy == 'timestamp_aware'
            or temporal_info['target_sec'] is not None
            or temporal_info['start_sec'] is not None
            or temporal_info['page'] is not None
            or temporal_info['slide'] is not None
        )

        if is_timestamp_query and units_by_id:
            target_sec = temporal_info.get('target_sec')
            range_start = temporal_info.get('start_sec')
            range_end = temporal_info.get('end_sec')
            target_page = temporal_info.get('page')
            target_slide = temporal_info.get('slide')

            # Score adjustments for existing results
            matched_uids = set()
            for r in results:
                u = units_by_id.get(r['unit_id'], {})
                u_start = u.get('timestamp_start')
                u_end = u.get('timestamp_end')
                u_page = u.get('page')
                u_slide = u.get('slide')

                if target_sec is not None and u_start is not None:
                    end_sec = u_end if u_end is not None else u_start + 15.0
                    if u_start <= target_sec <= end_sec:
                        r['final_score'] = min(1.0, r['final_score'] + 0.60)
                        r['temporal_exact'] = True
                        matched_uids.add(r['unit_id'])
                    else:
                        delta = min(abs(u_start - target_sec), abs(end_sec - target_sec))
                        if delta <= 90.0:
                            boost = 0.45 / (1.0 + delta / 25.0)
                            r['final_score'] = min(1.0, r['final_score'] + boost)
                            matched_uids.add(r['unit_id'])

                elif range_start is not None and range_end is not None and u_start is not None:
                    end_sec = u_end if u_end is not None else u_start + 15.0
                    if not (end_sec < range_start or u_start > range_end):
                        r['final_score'] = min(1.0, r['final_score'] + 0.55)
                        matched_uids.add(r['unit_id'])

                elif target_page is not None and u_page == target_page:
                    r['final_score'] = min(1.0, r['final_score'] + 0.50)
                    matched_uids.add(r['unit_id'])

                elif target_slide is not None and u_slide == target_slide:
                    r['final_score'] = min(1.0, r['final_score'] + 0.50)
                    matched_uids.add(r['unit_id'])

            # If the exact temporal unit was missed by textual search, find and inject it
            if target_sec is not None or target_page is not None or target_slide is not None:
                for uid, u in units_by_id.items():
                    if uid in matched_uids:
                        continue
                    if target_source_id and u.get('source_id') != target_source_id:
                        continue

                    u_start = u.get('timestamp_start')
                    u_end = u.get('timestamp_end')
                    if target_sec is not None and u_start is not None:
                        end_sec = u_end if u_end is not None else u_start + 15.0
                        if u_start <= target_sec <= end_sec:
                            results.append({
                                'unit_id': uid,
                                'final_score': 0.88,
                                'semantic_score': 0.0,
                                'lexical_score': 0.0,
                                'knowledge_confidence': u.get('confidence', 0.95),
                                'payload': {
                                    'knowledge_unit_id': uid,
                                    'source_id': u.get('source_id'),
                                    'modality': u.get('modality'),
                                    'timestamp_start': u_start,
                                    'timestamp_end': u_end,
                                    'content_preview': u.get('content', '')[:200],
                                    'from_temporal_search': True,
                                },
                            })
                            matched_uids.add(uid)
                    elif target_page is not None and u.get('page') == target_page:
                        results.append({
                            'unit_id': uid,
                            'final_score': 0.85,
                            'semantic_score': 0.0,
                            'lexical_score': 0.0,
                            'knowledge_confidence': u.get('confidence', 0.95),
                            'payload': {'knowledge_unit_id': uid, 'page': target_page},
                        })
                        matched_uids.add(uid)
                    elif target_slide is not None and u.get('slide') == target_slide:
                        results.append({
                            'unit_id': uid,
                            'final_score': 0.85,
                            'semantic_score': 0.0,
                            'lexical_score': 0.0,
                            'knowledge_confidence': u.get('confidence', 0.95),
                            'payload': {'knowledge_unit_id': uid, 'slide': target_slide},
                        })
                        matched_uids.add(uid)

        # 3. Knowledge Graph / VEKG Traversal
        if (strategy == 'knowledge_graph' or strategy == 'conceptual') and self.vekg is not None:
            graph_matches = self.vekg.traverse_related_concepts(
                query=query,
                threshold=0.35,
                source_id=target_source_id,
                max_results=top_k,
            )
            existing_ids = {r['unit_id'] for r in results}
            for gm in graph_matches:
                unit = gm['unit']
                if unit.id not in existing_ids:
                    results.append({
                        'unit_id': unit.id,
                        'final_score': round(gm['score'], 4),
                        'semantic_score': 0.0,
                        'lexical_score': 0.0,
                        'knowledge_confidence': unit.confidence,
                        'payload': {
                            'knowledge_unit_id': unit.id,
                            'source_id': unit.source_id,
                            'concept': unit.concept,
                            'modality': unit.modality,
                            'confidence': unit.confidence,
                            'status': unit.status,
                            'content_preview': unit.content[:200],
                            'graph_relations': gm.get('relations', []),
                        },
                        'from_vekg': True,
                    })
                else:
                    # Boost existing result that has graph connectivity
                    for r in results:
                        if r['unit_id'] == unit.id:
                            r['final_score'] = min(1.0, r['final_score'] * 1.25)
                            r['from_vekg'] = True
                            if 'payload' in r:
                                r['payload']['graph_relations'] = gm.get('relations', [])

        # Filter strictly by source_id when querying a single source
        if target_source_id:
            results = [
                r for r in results
                if units_by_id.get(r.get('unit_id'), {}).get('source_id') == target_source_id
                or r.get('payload', {}).get('source_id') == target_source_id
                or (not units_by_id.get(r.get('unit_id')) and not r.get('payload', {}).get('source_id'))
            ]

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
            'value', 'used', 'using', 'calculate', 'function', 'case', 'equation', 'rule',
            'slide', 'slides', 'lecture', 'video', 'course', 'material', 'notes',
            'document', 'page', 'work', 'stated', 'mentioned', 'according', 'instructor', 'professor',
            'discussed', 'happens', 'happened', 'say', 'says', 'talking', 'model', 'summary', 'overview',
        }

        # Check for temporal or page targets
        temporal_info = _extract_temporal_targets(query)
        is_temporal_lookup = (
            temporal_info['target_sec'] is not None
            or temporal_info['start_sec'] is not None
            or temporal_info['page'] is not None
            or temporal_info['slide'] is not None
        )
        if is_temporal_lookup:
            t_sec = temporal_info.get('target_sec')
            t_page = temporal_info.get('page')
            t_slide = temporal_info.get('slide')
            for ev in evidence_units:
                u_start = ev.get('timestamp_start')
                u_end = ev.get('timestamp_end')
                if t_sec is not None and u_start is not None:
                    end_sec = u_end if u_end is not None else u_start + 25.0
                    if (u_start - 15.0) <= t_sec <= (end_sec + 15.0):
                        return True, f"Temporal target {t_sec}s grounded in timestamp evidence ({u_start}-{u_end}s)"
                if t_page is not None and ev.get('page') == t_page:
                    return True, f"Page {t_page} grounded in document evidence"
                if t_slide is not None and ev.get('slide') == t_slide:
                    return True, f"Slide {t_slide} grounded in slide evidence"

        def _stem(w: str) -> str:
            w_str = w.lower().strip()
            if w_str.endswith('ies') and len(w_str) > 4:
                return w_str[:-3] + 'y'
            if w_str.endswith('es') and len(w_str) > 3:
                return w_str[:-2]
            if w_str.endswith('s') and not w_str.endswith('ss') and len(w_str) > 2:
                return w_str[:-1]
            return w_str

        q_tokens = re.findall(r'\b[a-zA-Z0-9_\^²³]{2,}\b', query.lower())
        content_tokens = [t for t in q_tokens if t not in STOPWORDS]
        subject_tokens = [t for t in content_tokens if t not in GENERIC_QUERY_TERMS and not t.isdigit()]

        ev_text = ' '.join(
            (str(e.get('concept', '')) + ' ' + str(e.get('text') or e.get('content') or '')).lower()
            for e in evidence_units
        )
        ev_words = {_stem(w) for w in re.findall(r'\b[a-zA-Z0-9_\^²³]{2,}\b', ev_text)}
        overlap_subj = [
            t for t in subject_tokens
            if _stem(t) in ev_words or re.search(r'\b' + re.escape(t) + r'\b', ev_text)
        ]

        if max_score < 0.20:
            return False, f"Relevance score {max_score:.2f} below minimum sufficiency threshold (0.20)"

        if len(subject_tokens) > 0 and len(overlap_subj) == 0:
            return False, f"Distinctive subject terms {subject_tokens} not grounded in retrieved evidence"

        return True, "Evidence sufficient"

    async def run(
        self,
        query: str,
        source_id: Optional[str],
        source_type: str,
        top_k: int = 5,
        include_conflicts: bool = True,
        conflicts: Optional[List[Dict[str, Any]]] = None,
        units_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
        requested_strategy: Optional[str] = None,
        modality_filter: Optional[str] = None,
        timestamp_filter: Optional[Dict[str, Any]] = None,
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
        routing = self.router.route(query, source_type, requested_strategy=requested_strategy)
        strategy = routing['strategy']
        top_k_eff = routing.get('top_k_override') or top_k
        active_modality_filter = modality_filter or routing.get('modality_filter')

        logger.info(
            'Query routed: type=%s strategy=%s top_k=%d requested=%s',
            routing['query_type'], strategy, top_k_eff, requested_strategy,
        )

        # 2. Retrieve
        results = await self.retriever.retrieve(
            query=query,
            source_id=source_id,
            strategy=strategy,
            top_k=top_k_eff * 2,  # over-retrieve then rerank
            modality_filter=active_modality_filter,
            units_by_id=units_by_id,
            timestamp_filter=timestamp_filter,
        )

        # 3. Rerank
        ranked = self.reranker.rerank(query, results, units_by_id)

        # 4. Select evidence
        selected = self.reranker.select_evidence(ranked, top_k=top_k)

        # 5. Build raw evidence units (strictly bounded to requested source unless all sources)
        raw_evidence_units = []
        is_all_sources = not source_id or source_id.lower() in ('all', 'all_sources', '*')
        for r in selected:
            payload = r.get('payload', {})
            unit = units_by_id.get(r['unit_id'], {})
            merged = {**payload, **unit, 'id': r['unit_id']}
            if is_all_sources or not merged.get('source_id') or merged.get('source_id') == source_id:
                raw_evidence_units.append(merged)

        # 6. VEKG correction traversal: substitute superseded units with active corrections
        evidence_units = []
        lineage_substitutions = []
        vekg_instance = getattr(self.retriever, 'vekg', None)
        for unit in raw_evidence_units:
            if unit.get('status') == 'superseded' and vekg_instance is not None:
                lineage = vekg_instance.get_lineage(unit.get('id', ''))
                active_u = lineage[0] if lineage else None
                if active_u:
                    active_dict = active_u.__dict__ if hasattr(active_u, '__dict__') else dict(active_u)
                    if not source_id or not active_dict.get('source_id') or active_dict.get('source_id') == source_id:
                        evidence_units.append(active_dict)
                        lineage_substitutions.append({
                            'superseded_id': unit.get('id'),
                            'active_id': active_dict.get('id'),
                            'concept': active_dict.get('concept'),
                            'reason': active_dict.get('correction_reason', 'Superseded version resolved via VEKG'),
                        })
                    else:
                        evidence_units.append(unit)
                else:
                    newer_id = next((uid for uid, u in units_by_id.items() if u.get('previous_version_id') == unit.get('id')), None)
                    if newer_id and newer_id in units_by_id:
                        newer_unit = {**units_by_id[newer_id], 'id': newer_id}
                        if not source_id or not newer_unit.get('source_id') or newer_unit.get('source_id') == source_id:
                            evidence_units.append(newer_unit)
                            lineage_substitutions.append({
                                'superseded_id': unit.get('id'),
                                'active_id': newer_id,
                                'concept': newer_unit.get('concept'),
                                'reason': newer_unit.get('correction_reason', 'Superseded version resolved via lineage ID'),
                            })
                        else:
                            evidence_units.append(unit)
                    else:
                        evidence_units.append(unit)
            else:
                evidence_units.append(unit)

        # Ensure conflicts are also strictly scoped to requested source unless searching all sources
        if not is_all_sources and source_id and conflicts:
            conflicts = [c for c in conflicts if not c.get('source_id') or c.get('source_id') == source_id]

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
            'lineage_substitutions': lineage_substitutions,
            'abstain': should_abstain,
            'abstention_reason': reason if should_abstain else None,
            'latency_ms': round(latency_ms, 2),
        }
