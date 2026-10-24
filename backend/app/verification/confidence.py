"""
Confidence and evidence-quality scoring for VisionRAG-X.

IMPORTANT METHODOLOGICAL NOTE — HEURISTIC RANKING SCORE, NOT CALIBRATED PROBABILITY:
The scores computed in this module are composite heuristic ranking indicators combining
extraction quality, multi-source agreement, recurrence, and dispute status.
They have NOT been calibrated on labeled validation data via isotonic regression,
Platt scaling, or Brier score minimization.

Do NOT interpret these numbers as Bayesian posterior probabilities that a claim is true.
Repeated mentions of a statement increase its topical recurrence score, but recurrence
does not independently establish factual authority or scientific correctness.
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """
    Transparent composite evidence-quality and retrieval ranking scorer.

    Heuristic formula:
        score = w_ext * extraction_quality
              + w_cm  * cross_modal_agreement
              + w_tmp * lexical_recurrence
              + w_vrf * verification_status

    All weights are configurable for ablation experiments.
    """

    DEFAULT_WEIGHTS: Dict[str, float] = {
        'extraction': 0.35,
        'cross_modal': 0.30,
        'temporal': 0.20,
        'verification': 0.15,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        # Normalise so weights always sum to 1
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        self._keyword_window_counts: Dict[str, int] = {}
        self._total_windows: int = 0

    def build_recurrence_index(self, windows: List[Dict[str, Any]]) -> None:
        """
        Build an inverted index of keyword occurrences across aligned windows.
        Tracks topical recurrence across windows (measures mention frequency, NOT truth).
        """
        self._keyword_window_counts = {}
        self._total_windows = len(windows)
        for w in windows:
            all_segs = (
                w.get('asr_segments', []) + w.get('ocr_segments', []) +
                w.get('vision_segments', []) + w.get('formula_segments', []) +
                w.get('code_segments', [])
            )
            w_text = ' '.join(str(s.get('text', '')) for s in all_segs)
            words = set(re.findall(r'\b[a-zA-Z]{4,}\b', w_text.lower()))
            for word in words:
                self._keyword_window_counts[word] = self._keyword_window_counts.get(word, 0) + 1

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    def _extraction_score(self, segment: Dict[str, Any]) -> float:
        """
        Extraction quality score based on extractor confidence and text noise.
        Penalises noisy OCR and degraded transcript spans.
        """
        raw = float(segment.get('confidence', 0.5))
        text = str(segment.get('text', '')).strip()

        # Check for garbled/noisy OCR text (high ratio of non-alphanumeric noise)
        if text and len(text) > 8:
            non_alphanumeric = len(re.findall(r'[^a-zA-Z0-9\s\.,;:!\?\-\(\)\/=\*\+]', text))
            noise_ratio = non_alphanumeric / len(text)
            if noise_ratio > 0.25:
                raw *= 0.6  # Downweight noisy extraction

        return max(0.0, min(1.0, raw))

    def _cross_modal_agreement(
        self,
        segment: Dict[str, Any],
        window: Dict[str, Any],
    ) -> float:
        """
        How well do other modalities in the same window agree with this segment?
        Uses token-overlap F1 between speech and slide text.
        """
        modality = segment.get('modality', '')
        seg_text = set(str(segment.get('text', '')).lower().split())
        if not seg_text:
            return 0.5  # neutral baseline when no text

        other_texts: List[str] = []
        if modality in ('asr', 'text'):
            other_texts = [s.get('text', '') for s in window.get('ocr_segments', [])]
        elif modality == 'ocr':
            other_texts = [s.get('text', '') for s in window.get('asr_segments', [])]
        else:
            return 0.6  # vision / formula / code neutral score

        if not other_texts:
            return 0.5

        other_tokens = set(' '.join(other_texts).lower().split())
        if not other_tokens:
            return 0.5

        intersection = seg_text & other_tokens
        precision = len(intersection) / len(seg_text)
        recall = len(intersection) / len(other_tokens)
        if precision + recall == 0:
            return 0.0
        f1 = 2 * precision * recall / (precision + recall)
        return f1

    def _temporal_consistency(
        self,
        segment: Dict[str, Any],
        window: Dict[str, Any],
        all_windows: Optional[List[Dict[str, Any]]] = None,
    ) -> float:
        """
        Calculates lexical recurrence across windows.

        Content mentioning concepts recurring across multiple windows receives
        a recurrence ratio up to 1.0, while single isolated mentions score 0.5 (neutral).
        NOTE: Recurrence measures lecture topic persistence, NOT empirical truth.
        """
        seg_text = segment.get('text', '')
        if not seg_text:
            return 0.5

        words = re.findall(r'\b[a-zA-Z]{4,}\b', seg_text.lower())
        if not words:
            return 0.5

        if self._keyword_window_counts and self._total_windows > 1:
            counts = [self._keyword_window_counts.get(w, 1) for w in words]
            avg_recurrence = sum(counts) / len(counts)
            recurrence_ratio = min(1.0, (avg_recurrence - 1) / max(1, min(4, self._total_windows - 1)))
            return round(0.50 + 0.50 * recurrence_ratio, 3)

        if all_windows and len(all_windows) > 1:
            kw_set = set(words)
            matching_windows = 0
            for w in all_windows:
                combined = ' '.join(
                    str(s.get('text', '')) for s in w.get('asr_segments', []) + w.get('ocr_segments', [])
                )
                if any(k in combined.lower() for k in kw_set):
                    matching_windows += 1
            ratio = matching_windows / len(all_windows)
            return round(min(1.0, 0.50 + 0.50 * (ratio * 2)), 3)

        return 0.5

    def _verification_score(
        self,
        segment: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
    ) -> float:
        """
        Verification status score.
        - Superseded claims are heavily penalized (cannot outrank corrections).
        - Verified corrections are rewarded.
        - Unverified candidates apply mild caution, not full penalty.
        - False positive conflicts are ignored.
        """
        status = segment.get('status')
        if status == 'superseded':
            return 0.20
        if status == 'verified' or segment.get('correction_reason'):
            return 1.0
        if status == 'disputed':
            return 0.40

        seg_timestamp = segment.get('timestamp_start') or segment.get('start')
        seg_modality = segment.get('modality', '')

        for conflict in conflicts:
            # Skip verified false positives
            if conflict.get('is_genuine_conflict') is False or conflict.get('verification_status') == 'false_positive':
                continue

            if seg_modality in conflict.get('sources', []):
                conflict_ts = conflict.get('timestamp')
                if conflict_ts is None or seg_timestamp is None:
                    continue
                if abs(float(conflict_ts) - float(seg_timestamp)) < 20.0:
                    is_candidate = conflict.get('is_candidate') or conflict.get('is_genuine_conflict') is None
                    if is_candidate:
                        # Mild cautionary score for unverified candidates
                        return 0.75
                    severity_penalty = {'high': 0.4, 'medium': 0.6, 'low': 0.8}.get(
                        conflict.get('severity', 'low'), 0.8
                    )
                    return severity_penalty
        return 1.0

    # ------------------------------------------------------------------
    # Public scoring methods
    # ------------------------------------------------------------------

    def score_breakdown(
        self,
        segment: Dict[str, Any],
        window: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
        all_windows: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Return the explicit score breakdown across all heuristic signals.
        Separates extraction quality, cross-modal agreement, recurrence, and status.
        """
        ext = self._extraction_score(segment)
        cm = self._cross_modal_agreement(segment, window)
        tmp = self._temporal_consistency(segment, window, all_windows=all_windows)
        vrf = self._verification_score(segment, conflicts)

        base_score = (
            self.weights['extraction'] * ext
            + self.weights['cross_modal'] * cm
            + self.weights['temporal'] * tmp
            + self.weights['verification'] * vrf
        )

        # Enforce rule: A superseded statement must never outrank an active correction,
        # even if the superseded statement was repeated many times across windows.
        if segment.get('status') == 'superseded':
            base_score = min(0.35, base_score * 0.4)

        heuristic_score = round(max(0.0, min(1.0, base_score)), 4)

        return {
            'heuristic_score': heuristic_score,
            'extraction_quality': round(ext, 3),
            'cross_modal_agreement': round(cm, 3),
            'lexical_recurrence': round(tmp, 3),
            'verification_status_score': round(vrf, 3),
            'is_calibrated_probability': False,
            'note': 'Heuristic ranking score; not a calibrated posterior probability of correctness.',
        }

    def score_segment(
        self,
        segment: Dict[str, Any],
        window: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
        all_windows: Optional[List[Dict[str, Any]]] = None,
    ) -> float:
        """Calculate composite evidence-quality ranking score for a single raw segment."""
        breakdown = self.score_breakdown(segment, window, conflicts, all_windows=all_windows)
        return breakdown['heuristic_score']

    def score_knowledge_unit(
        self,
        unit: Dict[str, Any],
        window: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
        all_windows: Optional[List[Dict[str, Any]]] = None,
    ) -> float:
        """
        Calculate composite evidence-quality ranking score for a processed knowledge unit.
        Uses the unit's own extraction confidence and status as the base.
        """
        pseudo_segment = {
            'confidence': unit.get('confidence', 0.5),
            'modality': unit.get('modality', ''),
            'text': unit.get('content', ''),
            'timestamp_start': unit.get('timestamp_start'),
            'status': unit.get('status'),
            'correction_reason': unit.get('correction_reason'),
        }
        return self.score_segment(pseudo_segment, window, conflicts, all_windows=all_windows)

    def explain(self, components: Dict[str, float]) -> str:
        """Return a human-readable explanation of an evidence-quality ranking breakdown."""
        total = sum(self.weights.get(k, 0.25) * v for k, v in components.items())
        parts = ', '.join(f'{k}: {v:.2f}' for k, v in components.items())
        return (
            f'Heuristic ranking score: {total:.3f} '
            f'(HEURISTIC RANKING SCORE, NOT A CALIBRATED PROBABILITY) '
            f'| Components: {parts}'
        )
