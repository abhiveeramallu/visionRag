"""
Cross-modal conflict detection for VisionRAG-X.

EXPERIMENTAL: Uses deterministic rules in the first version.
The interface is designed to allow an LLM-based verifier to replace
or augment the rule-based approach in future work.
"""
import re
import json
import logging
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# System prompt for LLM-assisted conflict verification
CONFLICT_VERIFICATION_PROMPT = """You are a conflict verification specialist for multimodal educational content.
Given a potential conflict detected between different modalities (speech transcript vs slide/OCR/visuals), evaluate whether there is a genuine factual contradiction.

STRICT EVALUATION CRITERIA:
1. "is_genuine_conflict": true if the claims directly contradict each other and cannot both be true simultaneously in context. false if they represent different aspects, approximations, complementary details, or different steps.
2. "resolution_status": "unresolved" (if both sources could be valid or no clear winner), "resolved" (if one explicitly corrects the other or slide/transcript has clear authoritative status), or "not_a_conflict" (if no genuine contradiction).
3. "resolution_explanation": A concise, clear explanation of the disagreement or why it is not a conflict.
4. "confidence": A float between 0.0 and 1.0 indicating confidence in this verification assessment.
5. "recommended_claim": The preferred claim if resolved, or null if unresolved.

Return ONLY a valid JSON object with the keys:
{
  "is_genuine_conflict": bool,
  "resolution_status": "unresolved" | "resolved" | "not_a_conflict",
  "resolution_explanation": str,
  "confidence": float,
  "recommended_claim": str | null
}"""

# Patterns for detecting algorithmic complexity notation.
# Capture group normalises whitespace but preserves the full inner expression.
COMPLEXITY_PATTERN = re.compile(r'O\s*\(([^)]+)\)', re.IGNORECASE)
NUMBER_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\b')

# Minimal normaliser for complexity strings: remove all whitespace and lower.
# This turns "n log n", "n Log N", "nlogn" into the same canonical form so
# that true matches are not reported as conflicts.
_NORM_COMPLEXITY_RE = re.compile(r'[\s*]+')


def _normalise_complexity(expr: str) -> str:
    """Lower-case and strip all whitespace / multiplication stars from a complexity expression."""
    return _NORM_COMPLEXITY_RE.sub('', expr.lower())


class ConflictDetector:
    """
    Cross-modal conflict detector.

    EXPERIMENTAL: First version uses deterministic rules.
    Interface is designed for future replacement with an LLM-based verifier.

    Detected conflict types:
    - complexity_disagreement: Different Big-O notations across modalities
    - numeric_disagreement: Different key numbers mentioned in ASR vs OCR
    - formula_contradiction: Significantly different mathematical expressions
    - factual_contradiction: Keyword-based contradictory statements
    """

    CONTRADICTION_PAIRS = [
        ({'correct', 'right', 'accurate', 'true'}, {'wrong', 'incorrect', 'error', 'mistake', 'false'}),
        ({'increases', 'grows', 'rises', 'larger', 'greater'}, {'decreases', 'shrinks', 'falls', 'smaller', 'less'}),
        ({'always', 'every', 'all'}, {'never', 'none', 'no'}),
        ({'converges', 'stable'}, {'diverges', 'unstable'}),
    ]

    def __init__(self, settings: Any, llm_client: Optional[Any] = None):
        self.settings = settings
        self.enabled: bool = getattr(settings, 'conflict_detection_enabled', True)
        self.severity_threshold: float = getattr(settings, 'conflict_severity_threshold', 0.5)
        self.llm_client = llm_client

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_complexity(self, text: str) -> List[str]:
        """Extract and normalise Big-O complexity expressions, e.g. ['nlogn', 'n^2']."""
        return [_normalise_complexity(m.group(1)) for m in COMPLEXITY_PATTERN.finditer(text)]

    def _extract_numbers(self, text: str) -> List[float]:
        """Extract numeric values from text."""
        return [float(m.group()) for m in NUMBER_PATTERN.finditer(text)]

    def _text_similarity(self, a: str, b: str) -> float:
        """Normalised text similarity ratio (0–1)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _calculate_severity(self, conflict_type: str, source_confidence: float) -> str:
        """Derive severity from conflict type and source confidence."""
        if conflict_type in ('complexity_disagreement', 'formula_contradiction'):
            return 'high'
        if conflict_type == 'numeric_disagreement' and source_confidence > 0.8:
            return 'medium'
        if conflict_type == 'factual_contradiction':
            return 'medium'
        return 'low'

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def _detect_complexity_conflict(
        self,
        text_a: str,
        text_b: str,
        modality_a: str,
        modality_b: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        comp_a = self._extract_complexity(text_a)
        comp_b = self._extract_complexity(text_b)
        if not comp_a or not comp_b:
            return None

        # 1. Scope / Assumption Check
        # Distinguish genuine contradictions from compatible statements describing different data structures or cases
        SCOPE_ASSUMPTION_PAIRS = [
            ("balanced", "unbalanced"),
            ("avl", "unbalanced"),
            ("red-black", "unbalanced"),
            ("red black", "unbalanced"),
            ("skewed", "balanced"),
            ("degenerate", "balanced"),
            ("worst case", "average case"),
            ("worst case", "best case"),
            ("average case", "best case"),
            ("worst-case", "average-case"),
            ("worst-case", "best-case"),
            ("average-case", "best-case"),
            ("time", "space"),
            ("height", "search"),
            ("height", "traversal"),
            ("search", "insert"),
            ("search", "delete"),
            ("insert", "delete"),
            ("sorted", "unsorted"),
            ("sparse", "dense"),
            ("directed", "undirected"),
            ("acyclic", "cyclic"),
        ]
        text_a_lower = text_a.lower()
        text_b_lower = text_b.lower()
        def _has_phrase(phrase: str, text: str) -> bool:
            return bool(re.search(r'\b' + re.escape(phrase) + r'\b', text, re.IGNORECASE))

        for term1, term2 in SCOPE_ASSUMPTION_PAIRS:
            if (_has_phrase(term1, text_a_lower) and _has_phrase(term2, text_b_lower)) or \
               (_has_phrase(term2, text_a_lower) and _has_phrase(term1, text_b_lower)):
                logger.debug(
                    "Complexity statements differ due to scope/assumptions (%s vs %s); compatible statement, not a conflict.",
                    term1, term2
                )
                return None

        # Compare normalised forms — prevents O(n) vs O(n^2) false-negatives
        # where the shorter string is a prefix of the longer one.
        for ca in comp_a:
            for cb in comp_b:
                if ca != cb:
                    severity = self._calculate_severity('complexity_disagreement', 0.9)
                    
                    # Check for classic BST search complexity contradiction:
                    # Unbalanced BST worst-case search claiming O(log n) vs O(n)
                    is_bst_search = any(w in text_a_lower or w in text_b_lower for w in ("bst", "binary search tree"))
                    resolution = None
                    resolved = False
                    if is_bst_search and (("logn" in ca and "n" == cb) or ("logn" in cb and "n" == ca)):
                        if "unbalanced" in text_a_lower or "unbalanced" in text_b_lower:
                            resolved = True
                            resolution = (
                                "An unbalanced BST degenerates to a linear chain in the worst case yielding O(n) search; "
                                "balanced BSTs (e.g. AVL, Red-Black) maintain O(log n) search complexity."
                            )

                    return {
                        'type': 'complexity_disagreement',
                        'sources': [modality_a, modality_b],
                        'claims': [
                            f'O({ca}) [{modality_a}]',
                            f'O({cb}) [{modality_b}]',
                        ],
                        'severity': severity,
                        'confidence': 0.85,
                        'resolved': resolved,
                        'resolution': resolution,
                        **context,
                    }
        return None

    def _detect_formula_contradiction(
        self,
        text_a: str,
        text_b: str,
        modality_a: str,
        modality_b: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Detect conflicting mathematical formulas / equations between modalities.

        Employs a multi-stage symbolic and contextual comparison:
        1. Contextual Regime / Assumption Check:
           If texts explicitly specify different regimes (e.g. relativistic vs
           non-relativistic, worst-case vs average-case), formulas are considered
           conditional variations rather than direct contradictions.
        2. Unit Normalization:
           Quantities with convertible units (e.g., 10 m/s vs 36 km/h) are normalized
           to SI base units before comparison.
        3. Symbolic Equivalence via SymPy:
           Expressions are parsed symbolically to verify commutativity, associativity,
           and distributive transformations (e.g., E = m*c^2 vs E = c^2*m,
           or 0.5*m*v^2 vs (m*v^2)/2).
        4. Equation Rearrangement:
           Different algebraic arrangements of the same governing equation
           (e.g., F = m*a vs a = F/m) are verified by solving for common symbols.
        5. Safe Parsing Fallback:
           Malformed equations, unsupported syntax, or ambiguous notation return
           None (uncertain/inconclusive) rather than asserting an unverified contradiction.
        """
        # 1. Check for differing explicit contextual assumptions
        ASSUMPTION_PAIRS = [
            ("relativistic", "non-relativistic"),
            ("relativistic", "classical"),
            ("classical", "quantum"),
            ("worst case", "average case"),
            ("worst case", "best case"),
            ("average case", "best case"),
            ("isothermal", "adiabatic"),
            ("ideal", "real"),
            ("frictionless", "friction"),
        ]
        text_a_lower = text_a.lower()
        text_b_lower = text_b.lower()
        for term1, term2 in ASSUMPTION_PAIRS:
            if (term1 in text_a_lower and term2 in text_b_lower) or (term2 in text_a_lower and term1 in text_b_lower):
                logger.debug("Formulas in %s and %s differ due to assumptions (%s vs %s); not a contradiction.", modality_a, modality_b, term1, term2)
                return None

        # Extract equations matching word/symbol = expression
        EQ_PATTERN = re.compile(r'([A-Za-z]\w*)\s*=\s*([\w\.\+\-\*/\^\(\)\s²³·×]+)', re.IGNORECASE)
        eqs_a = {m.group(1).lower(): m.group(2).strip() for m in EQ_PATTERN.finditer(text_a)}
        eqs_b = {m.group(1).lower(): m.group(2).strip() for m in EQ_PATTERN.finditer(text_b)}
        if not eqs_a or not eqs_b:
            return None

        MATH_STOPWORDS = {
            'where', 'when', 'for', 'with', 'without', 'in', 'at', 'as', 'is', 'the', 'and', 'which', 'because'
        }

        def _clean_rhs_math(raw: str) -> str:
            tokens = raw.split()
            math_tokens = []
            for t in tokens:
                clean_word = t.strip(".,;:!?()").lower()
                if len(clean_word) > 1 and clean_word in MATH_STOPWORDS:
                    break
                math_tokens.append(t)
            cleaned = " ".join(math_tokens).rstrip(".,;:!?")
            return cleaned if cleaned else raw.rstrip(".,;:!?")

        # Unit factors to base SI
        UNIT_FACTORS = {
            'm/s': 1.0,
            'km/h': 1000.0 / 3600.0,
            'km/hr': 1000.0 / 3600.0,
            'm': 1.0,
            'cm': 0.01,
            'km': 1000.0,
            'mm': 0.001,
            'kg': 1.0,
            'g': 0.001,
            's': 1.0,
            'min': 60.0,
            'hr': 3600.0,
            'h': 3600.0,
        }
        UNIT_REGEX = re.compile(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z/]+)$')

        def parse_unit_val(s: str) -> Optional[float]:
            m = UNIT_REGEX.match(s.strip())
            if m:
                val = float(m.group(1))
                unit = m.group(2).lower()
                if unit in UNIT_FACTORS:
                    return val * UNIT_FACTORS[unit]
            return None

        # Check direct LHS match
        common_lhs = set(eqs_a) & set(eqs_b)
        if common_lhs:
            for lhs in common_lhs:
                raw_rhs_a = eqs_a[lhs]
                raw_rhs_b = eqs_b[lhs]
                clean_rhs_a = _clean_rhs_math(raw_rhs_a)
                clean_rhs_b = _clean_rhs_math(raw_rhs_b)

                # 2. Check Unit Equivalence
                unit_a = parse_unit_val(clean_rhs_a)
                unit_b = parse_unit_val(clean_rhs_b)
                if unit_a is not None and unit_b is not None:
                    if abs(unit_a - unit_b) < 1e-4:
                        # Equivalent under unit conversion
                        continue
                    else:
                        severity = self._calculate_severity('formula_contradiction', 0.85)
                        return {
                            'type': 'formula_contradiction',
                            'sources': [modality_a, modality_b],
                            'claims': [
                                f'{lhs} = {clean_rhs_a} [{modality_a}]',
                                f'{lhs} = {clean_rhs_b} [{modality_b}]',
                            ],
                            'severity': severity,
                            'confidence': 0.85,
                            'candidate_rationale': f'Unit mismatch: {clean_rhs_a} vs {clean_rhs_b}',
                            **context,
                        }

                # 3. Symbolic Comparison with SymPy
                is_symbolically_equiv = False
                is_symbolically_diff = False
                try:
                    import sympy
                    from sympy.parsing.sympy_parser import (
                        parse_expr,
                        standard_transformations,
                        implicit_multiplication_application,
                    )
                    trans = standard_transformations + (implicit_multiplication_application,)
                    norm_a = clean_rhs_a.replace('^', '**').replace('²', '**2').replace('³', '**3').replace('·', '*').replace('×', '*')
                    norm_b = clean_rhs_b.replace('^', '**').replace('²', '**2').replace('³', '**3').replace('·', '*').replace('×', '*')

                    expr_a = parse_expr(norm_a, transformations=trans)
                    expr_b = parse_expr(norm_b, transformations=trans)
                    diff = sympy.simplify(expr_a - expr_b)
                    if diff == 0:
                        is_symbolically_equiv = True
                    else:
                        is_symbolically_diff = True
                except Exception as e:
                    logger.debug("SymPy could not parse formula RHS (%s vs %s): %s", clean_rhs_a, clean_rhs_b, e)

                if is_symbolically_equiv:
                    continue

                if is_symbolically_diff:
                    severity = self._calculate_severity('formula_contradiction', 0.9)
                    return {
                        'type': 'formula_contradiction',
                        'sources': [modality_a, modality_b],
                        'claims': [
                            f'{lhs} = {clean_rhs_a} [{modality_a}]',
                            f'{lhs} = {clean_rhs_b} [{modality_b}]',
                        ],
                        'severity': severity,
                        'confidence': 0.85,
                        'candidate_rationale': f'Symbolic mathematical disagreement for {lhs}',
                        **context,
                    }

        # 4. Check for Algebraic Rearrangements across different LHS
        # E.g., F = m * a vs a = F / m
        for lhs_a, rhs_a in eqs_a.items():
            for lhs_b, rhs_b in eqs_b.items():
                if lhs_a != lhs_b:
                    try:
                        import sympy
                        from sympy.parsing.sympy_parser import (
                            parse_expr,
                            standard_transformations,
                            implicit_multiplication_application,
                        )
                        trans = standard_transformations + (implicit_multiplication_application,)
                        norm_la = lhs_a.replace('^', '**').replace('²', '**2')
                        norm_ra = rhs_a.replace('^', '**').replace('²', '**2').replace('·', '*').replace('×', '*')
                        norm_lb = lhs_b.replace('^', '**').replace('²', '**2')
                        norm_rb = rhs_b.replace('^', '**').replace('²', '**2').replace('·', '*').replace('×', '*')

                        eq_expr_a = parse_expr(f'({norm_la}) - ({norm_ra})', transformations=trans)
                        eq_expr_b = parse_expr(f'({norm_lb}) - ({norm_rb})', transformations=trans)

                        common_symbols = eq_expr_a.free_symbols & eq_expr_b.free_symbols
                        if common_symbols and len(common_symbols) >= 2:
                            target_sym = next(iter(common_symbols))
                            sol_a = sympy.solve(eq_expr_a, target_sym)
                            sol_b = sympy.solve(eq_expr_b, target_sym)
                            if sol_a and sol_b and len(sol_a) == len(sol_b):
                                if all(sympy.simplify(sa - sb) == 0 for sa, sb in zip(sol_a, sol_b)):
                                    # Proved algebraically equivalent rearrangement!
                                    continue
                    except Exception:
                        pass

        return None

    def _detect_numeric_conflict(
        self,
        text_a: str,
        text_b: str,
        modality_a: str,
        modality_b: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        nums_a = set(self._extract_numbers(text_a))
        nums_b = set(self._extract_numbers(text_b))
        if not nums_a or not nums_b:
            return None
        only_a = nums_a - nums_b
        only_b = nums_b - nums_a
        # Only flag if there are differing numbers and the sets aren't huge
        if only_a and only_b and len(only_a) <= 3:
            severity = self._calculate_severity('numeric_disagreement', 0.75)
            return {
                'type': 'numeric_disagreement',
                'sources': [modality_a, modality_b],
                'claims': [
                    f'{modality_a} mentions: {sorted(only_a)}',
                    f'{modality_b} mentions: {sorted(only_b)}',
                ],
                'severity': severity,
                'confidence': 0.65,
                **context,
            }
        return None

    def _detect_factual_contradiction(
        self,
        text_a: str,
        text_b: str,
        modality_a: str,
        modality_b: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        for pos_set, neg_set in self.CONTRADICTION_PAIRS:
            a_pos = words_a & pos_set
            b_neg = words_b & neg_set
            a_neg = words_a & neg_set
            b_pos = words_b & pos_set
            if (a_pos and b_neg) or (a_neg and b_pos):
                severity = self._calculate_severity('factual_contradiction', 0.6)
                return {
                    'type': 'factual_contradiction',
                    'sources': [modality_a, modality_b],
                    'claims': [
                        f'{modality_a}: "{text_a[:120].strip()}"',
                        f'{modality_b}: "{text_b[:120].strip()}"',
                    ],
                    'severity': severity,
                    'confidence': 0.55,
                    **context,
                }
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_in_window(self, window: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect conflicts within a single aligned window.

        Compares ASR and OCR text in the same temporal/spatial window.
        Returns a list of conflict dicts (may be empty).
        """
        if not self.enabled:
            return []

        asr_segs = window.get('asr_segments', [])
        ocr_segs = window.get('ocr_segments', [])

        asr_text = ' '.join(str(s.get('text', '')) for s in asr_segs).strip()
        ocr_text = ' '.join(str(s.get('text', '')) for s in ocr_segs).strip()

        if not asr_text or not ocr_text:
            return []

        context: Dict[str, Any] = {
            'timestamp': window.get('window_start'),
            'page': window.get('page'),
            'source_id': window.get('source_id'),
        }

        # The "asr_segments" bucket holds real spoken-word ASR for video/audio
        # sources, but holds plain document text (modality='text') for PDFs and
        # PPTs — label the conflict with each side's *actual* modality instead
        # of always saying "asr", or a PDF-only conflict misleadingly implies
        # the source had speech.
        modality_a = (asr_segs[0].get('modality') or 'asr') if asr_segs else 'asr'
        modality_b = (ocr_segs[0].get('modality') or 'ocr') if ocr_segs else 'ocr'

        # Check high-precision structural conflicts first (complexity, formula, numeric).
        # These can occur even when surrounding text is largely identical (e.g., "O(n)" vs "O(n^2)").
        for check_fn in (
            self._detect_complexity_conflict,
            self._detect_formula_contradiction,
            self._detect_numeric_conflict,
        ):
            conflict = check_fn(asr_text, ocr_text, modality_a, modality_b, context)
            if conflict:
                return [conflict]

        # For general factual contradictions, skip windows where the modalities already agree closely.
        if self._text_similarity(asr_text, ocr_text) > 0.80:
            return []

        conflict = self._detect_factual_contradiction(asr_text, ocr_text, modality_a, modality_b, context)
        if conflict:
            return [conflict]

        return []

    def detect_all(self, windows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run conflict detection across all aligned windows."""
        all_conflicts: List[Dict[str, Any]] = []
        for window in windows:
            all_conflicts.extend(self.detect_in_window(window))
        logger.info(
            'Conflict detection complete: %d conflicts found in %d windows',
            len(all_conflicts),
            len(windows),
        )
        return all_conflicts

    def detect_between_claims(
        self,
        text_a: str,
        text_b: str,
        modality_a: str = "text",
        modality_b: str = "text",
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Detect conflicts directly between two arbitrary claims or statements.

        Can be used across different modalities, different timestamps, or different sources.
        """
        if not self.enabled or not text_a or not text_b:
            return None

        ctx = context or {}

        # 1. Structural checks
        for check_fn in (
            self._detect_complexity_conflict,
            self._detect_formula_contradiction,
            self._detect_numeric_conflict,
        ):
            conflict = check_fn(text_a, text_b, modality_a, modality_b, ctx)
            if conflict:
                return conflict

        # 2. Semantic / factual checks
        if self._text_similarity(text_a, text_b) > 0.85:
            return None

        return self._detect_factual_contradiction(text_a, text_b, modality_a, modality_b, ctx)

    def detect_between_units(
        self,
        unit_a: Any,
        unit_b: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Compare two Knowledge Units (can be from different sources or pages)
        and determine whether they present contradictory claims on the same topic.
        """
        if not self.enabled:
            return None

        # Extract text and modalities
        text_a = getattr(unit_a, 'content', '') or ''
        text_b = getattr(unit_b, 'content', '') or ''
        mod_a = getattr(unit_a, 'modality', 'text') or 'text'
        mod_b = getattr(unit_b, 'modality', 'text') or 'text'
        id_a = getattr(unit_a, 'id', str(unit_a))
        id_b = getattr(unit_b, 'id', str(unit_b))
        src_a = getattr(unit_a, 'source_id', None)
        src_b = getattr(unit_b, 'source_id', None)

        context = {
            'unit_ids': [id_a, id_b],
            'source_id': src_a,
            'source_id_b': src_b,
            'is_cross_source': src_a != src_b,
        }

        conflict = self.detect_between_claims(text_a, text_b, mod_a, mod_b, context)
        if conflict:
            conflict['unit_ids'] = [id_a, id_b]
        return conflict

    # ------------------------------------------------------------------
    # LLM-assisted conflict verification
    # ------------------------------------------------------------------

    async def verify_with_llm(
        self,
        conflict: Dict[str, Any],
        context: str,
        llm_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Verify and calibrate a detected conflict using an LLM.

        Analyzes candidate conflicting claims against surrounding context:
        - Confirms whether there is a genuine factual contradiction.
        - Identifies whether one claim corrects or supersedes another.
        - Determines resolution status (resolved, unresolved, not_a_conflict).
        - Estimates confidence and provides an explanation.

        Fallback behavior:
        If LLM is unconfigured, disabled, or fails, falls back gracefully to
        preserving the rule-detected conflict with status 'unresolved'.
        """
        # Check configuration before attempting to construct LLMClient
        is_configured = False
        try:
            is_configured = getattr(self.settings, 'is_llm_configured', lambda: False)()
        except Exception:
            is_configured = False

        client = llm_client or self.llm_client
        if not is_configured:
            return {
                **conflict,
                'llm_verified': False,
                'is_candidate': True,
                'is_genuine_conflict': None,  # Explicitly unconfirmed: candidate status preserved
                'verification_status': 'unverified',
                'status': 'candidate',
                'candidate_rationale': conflict.get('candidate_rationale') or conflict.get('resolution') or 'Candidate conflict flagged by rule-based heuristic.',
                'resolution': 'Unverified candidate conflict (LLM provider not configured).',
                'resolved': False,
            }

        if client is None:
            try:
                from app.generation.llm import LLMClient
                client = LLMClient(self.settings)
            except Exception as e:
                logger.debug('Could not initialize LLMClient for conflict verification: %s', e)
                return {
                    **conflict,
                    'llm_verified': False,
                    'is_candidate': True,
                    'is_genuine_conflict': None,
                    'verification_status': 'unverified',
                    'status': 'candidate',
                    'candidate_rationale': conflict.get('candidate_rationale') or conflict.get('resolution') or 'Candidate conflict flagged by rule-based heuristic.',
                    'resolution': f'Unverified candidate conflict (client init failed: {e})',
                    'resolved': False,
                }

        claims_str = '\n'.join(f'- {claim}' for claim in conflict.get('claims', []))
        sources_str = ', '.join(conflict.get('sources', []))
        user_prompt = (
            f"CONFLICT TYPE: {conflict.get('type', 'disagreement')}\n"
            f"SOURCES: {sources_str}\n"
            f"CLAIMS:\n{claims_str}\n\n"
            f"SURROUNDING CONTEXT:\n{context}\n\n"
            "Assess whether these claims represent a genuine contradiction in this context."
        )

        try:
            raw = await client.complete(
                system_prompt=CONFLICT_VERIFICATION_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=600,
                json_mode=True,
            )
            cleaned = raw.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            parsed = json.loads(cleaned)

            raw_genuine = parsed.get('is_genuine_conflict')
            is_genuine: Optional[bool]
            if raw_genuine is None:
                is_genuine = None
            else:
                is_genuine = bool(raw_genuine)

            status = parsed.get('resolution_status', 'unresolved')
            resolved = status == 'resolved'
            explanation = parsed.get('resolution_explanation', '')
            calibrated_conf = float(parsed.get('confidence', conflict.get('confidence', 0.5)))
            recommended = parsed.get('recommended_claim')

            if is_genuine is True:
                verification_status = 'verified_resolved' if resolved else 'verified_contradiction'
            elif is_genuine is False:
                verification_status = 'false_positive'
            else:
                verification_status = 'inconclusive'

            return {
                **conflict,
                'llm_verified': True,
                'is_candidate': is_genuine is None,
                'is_genuine_conflict': is_genuine,
                'verification_status': verification_status,
                'resolution': explanation,
                'candidate_rationale': conflict.get('candidate_rationale') or 'Rule-based heuristic candidate',
                'resolved': resolved,
                'confidence': round(calibrated_conf, 3),
                'recommended_claim': recommended,
                'status': status,
            }
        except Exception as e:
            logger.warning('LLM conflict verification failed: %s', e)
            return {
                **conflict,
                'llm_verified': False,
                'is_candidate': True,
                'is_genuine_conflict': None,  # Verification failed: preserve as inconclusive candidate
                'verification_status': 'inconclusive',
                'status': 'inconclusive',
                'candidate_rationale': conflict.get('candidate_rationale') or conflict.get('resolution') or 'Candidate conflict flagged by rule-based heuristic.',
                'resolution': f'Inconclusive candidate conflict preserved (verification error: {e})',
                'resolved': False,
            }

    async def verify_all_with_llm(
        self,
        conflicts: List[Dict[str, Any]],
        context_by_window: Dict[str, str],
        filter_false_positives: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Verify all candidate conflicts.

        When filter_false_positives is True:
        - Filters out verified false positives (is_genuine_conflict is False).
        - Preserves verified genuine contradictions (is_genuine_conflict is True).
        - Preserves unverified and inconclusive candidates (is_genuine_conflict is None).
        """
        verified: List[Dict[str, Any]] = []
        for c in conflicts:
            w_id = c.get('window_id', '')
            ctx = context_by_window.get(w_id, '')
            res = await self.verify_with_llm(c, ctx)
            if filter_false_positives:
                if res.get('is_genuine_conflict') is False or res.get('verification_status') == 'false_positive':
                    continue
            verified.append(res)
        return verified
