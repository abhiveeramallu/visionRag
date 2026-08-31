"""
Confidence scoring for VisionRAG-X.

EXPERIMENTAL: This is a 'system confidence score', NOT a calibrated probability.
The formula and weights have not been formally evaluated against ground truth.
Treat scores as relative indicators only.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """
    Transparent composite confidence scorer.

    IMPORTANT — NOT A CALIBRATED PROBABILITY:
    This score is a weighted combination of heuristic signals.
    It has not been validated against labelled data.
    Use it for relative ranking, not as an absolute probability estimate.

    Default formula:
        score = w_ext * extraction_confidence
              + w_cm  * cross_modal_agreement
              + w_tmp * temporal_consistency
              + w_vrf * verification_confidence

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

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    def _extraction_score(self, segment: Dict[str, Any]) -> float:
        """Raw extraction confidence from the ASR/OCR extractor (0–1)."""
        raw = float(segment.get('confidence', 0.5))
        return max(0.0, min(1.0, raw))

    def _cross_modal_agreement(
        self,
        segment: Dict[str, Any],
        window: Dict[str, Any],
    ) -> float:
        """
        How well do other modalities in the same window agree with this segment?

        EXPERIMENTAL: Uses simple token-overlap F1 between ASR and OCR text.
        A future version could use semantic similarity instead.
        """
        modality = segment.get('modality', '')
        seg_text = set(str(segment.get('text', '')).lower().split())
        if not seg_text:
            return 0.5  # neutral when no text

        other_texts: List[str] = []
        if modality == 'asr':
            other_texts = [s.get('text', '') for s in window.get('ocr_segments', [])]
        elif modality == 'ocr':
            other_texts = [s.get('text', '') for s in window.get('asr_segments', [])]
        else:
            # vision / formula / code — neutral score for now
            return 0.6

        if not other_texts:
            return 0.5  # no other modality present — neutral

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
    ) -> float:
        """
        How consistently does this content appear across windows?

        NOTE: This is a placeholder returning 0.5 (neutral).
        A proper implementation would track concept recurrence across multiple
        windows and award higher scores to consistently repeated content.
        This is left as a TODO for future experimental work.
        """
        return 0.5  # TODO: implement cross-window recurrence tracking

    def _verification_score(
        self,
        segment: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
    ) -> float:
        """
        Penalise segments that are involved in a detected conflict.
        A conflict-free segment scores 1.0; each conflict reduces the score.
        """
        seg_timestamp = segment.get('timestamp_start') or segment.get('start')
        seg_modality = segment.get('modality', '')

        for conflict in conflicts:
            if seg_modality in conflict.get('sources', []):
                # Check if conflict is in the same temporal region
                conflict_ts = conflict.get('timestamp')
                if conflict_ts is None or seg_timestamp is None:
                    return 0.5
                if abs(float(conflict_ts) - float(seg_timestamp)) < 20.0:
                    severity_penalty = {'high': 0.4, 'medium': 0.6, 'low': 0.8}.get(
                        conflict.get('severity', 'low'), 0.8
                    )
                    return severity_penalty
        return 1.0

    # ------------------------------------------------------------------
    # Public scoring methods
    # ------------------------------------------------------------------

    def score_segment(
        self,
        segment: Dict[str, Any],
        window: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
    ) -> float:
        """Calculate composite confidence score for a single raw segment."""
        components = {
            'extraction': self._extraction_score(segment),
            'cross_modal': self._cross_modal_agreement(segment, window),
            'temporal': self._temporal_consistency(segment, window),
            'verification': self._verification_score(segment, conflicts),
        }
        score = sum(self.weights[k] * v for k, v in components.items())
        return round(max(0.0, min(1.0, score)), 4)

    def score_knowledge_unit(
        self,
        unit: Dict[str, Any],
        window: Dict[str, Any],
        conflicts: List[Dict[str, Any]],
    ) -> float:
        """
        Calculate composite confidence score for a processed knowledge unit.
        Uses the unit's own extraction confidence as the base.
        """
        # Treat the unit dict like a segment for shared logic
        pseudo_segment = {
            'confidence': unit.get('confidence', 0.5),
            'modality': unit.get('modality', ''),
            'text': unit.get('content', ''),
            'timestamp_start': unit.get('timestamp_start'),
        }
        return self.score_segment(pseudo_segment, window, conflicts)

    def explain(self, components: Dict[str, float]) -> str:
        """Return a human-readable explanation of a confidence score breakdown."""
        total = sum(self.weights[k] * v for k, v in components.items())
        parts = ', '.join(f'{k}: {v:.2f}' for k, v in components.items())
        return (
            f'System confidence: {total:.3f} '
            f'(NOT a calibrated probability — for ranking only) '
            f'| Components: {parts}'
        )
