"""
Cross-modal conflict detection for VisionRAG-X.

EXPERIMENTAL: Uses deterministic rules in the first version.
The interface is designed to allow an LLM-based verifier to replace
or augment the rule-based approach in future work.
"""
import re
import logging
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Patterns for detecting algorithmic complexity notation
COMPLEXITY_PATTERN = re.compile(r'O\s*\(([^)]+)\)', re.IGNORECASE)
NUMBER_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\b')


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

    def __init__(self, settings: Any):
        self.settings = settings
        self.enabled: bool = getattr(settings, 'conflict_detection_enabled', True)
        self.severity_threshold: float = getattr(settings, 'conflict_severity_threshold', 0.5)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_complexity(self, text: str) -> List[str]:
        """Extract Big-O complexity strings, e.g. ['n log n', 'n^2']."""
        return [m.group(1).strip() for m in COMPLEXITY_PATTERN.finditer(text)]

    def _extract_numbers(self, text: str) -> List[float]:
        """Extract numeric values from text."""
        return [float(m.group()) for m in NUMBER_PATTERN.finditer(text)]

    def _text_similarity(self, a: str, b: str) -> float:
        """Normalised text similarity ratio (0–1)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _calculate_severity(self, conflict_type: str, source_confidence: float) -> str:
        """Derive severity from conflict type and source confidence."""
        if conflict_type == 'complexity_disagreement':
            return 'high'
        if conflict_type == 'formula_contradiction':
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
        for ca in comp_a:
            for cb in comp_b:
                if ca.replace(' ', '') != cb.replace(' ', ''):
                    severity = self._calculate_severity('complexity_disagreement', 0.9)
                    return {
                        'type': 'complexity_disagreement',
                        'sources': [modality_a, modality_b],
                        'claims': [
                            f'O({ca}) [{modality_a}]',
                            f'O({cb}) [{modality_b}]',
                        ],
                        'severity': severity,
                        'confidence': 0.85,
                        **context,
                    }
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

        # Skip windows where the two modalities already agree well
        if self._text_similarity(asr_text, ocr_text) > 0.80:
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

        for check_fn in (
            self._detect_complexity_conflict,
            self._detect_numeric_conflict,
            self._detect_factual_contradiction,
        ):
            conflict = check_fn(asr_text, ocr_text, modality_a, modality_b, context)
            if conflict:
                return [conflict]  # one conflict per window-pair is sufficient

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

    # ------------------------------------------------------------------
    # Interface for future LLM-based verifier
    # ------------------------------------------------------------------

    async def verify_with_llm(self, conflict: Dict[str, Any], context: str) -> Dict[str, Any]:
        """
        LLM-based conflict verification — NOT YET IMPLEMENTED.

        Implement this method to replace or augment rule-based detection
        with an LLM that can reason about semantic meaning.
        """
        raise NotImplementedError(
            'LLM-based conflict verification is not yet implemented. '
            'To add it: inject an LLMClient and call it here with the '
            'conflict dict and surrounding context string.'
        )
