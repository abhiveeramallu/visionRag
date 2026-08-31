"""
Provenance tracking for VisionRAG-X.

Links answer claims back to specific source segments, modalities, and timestamps.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _format_timestamp(seconds: Optional[float]) -> str:
    """Convert float seconds to MM:SS string."""
    if seconds is None:
        return ''
    total = int(seconds)
    mins, secs = divmod(total, 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f'{hours:02d}:{mins:02d}:{secs:02d}'
    return f'{mins:02d}:{secs:02d}'


class ProvenanceTracker:
    """
    Builds provenance chains linking answer evidence to source material.

    Every evidence item returned to the user carries:
    - The exact text excerpt
    - Source ID and title
    - Modality (ASR / OCR / Vision / Formula / Code)
    - Temporal location (timestamp) or spatial location (page / slide)
    - Extraction confidence
    - Knowledge unit ID and version
    - Status (active / superseded / disputed / verified)
    """

    def build_provenance(
        self,
        answer: str,
        retrieved_units: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Build a provenance list from retrieved knowledge units.

        Parameters
        ----------
        answer : str
            The generated answer (used for future claim-linking).
        retrieved_units : list of dict
            Processed knowledge unit dicts.
        query : str
            The original user query.

        Returns
        -------
        List of evidence dicts compatible with EvidenceItem response schema.
        """
        provenance: List[Dict[str, Any]] = []
        for unit in retrieved_units:
            item: Dict[str, Any] = {
                'text': unit.get('content', ''),
                'source_id': unit.get('source_id', ''),
                'modality': unit.get('modality', 'unknown'),
                'timestamp_start': unit.get('timestamp_start'),
                'timestamp_end': unit.get('timestamp_end'),
                'page': unit.get('page'),
                'slide': unit.get('slide'),
                'confidence': unit.get('confidence', 0.5),
                'knowledge_unit_id': unit.get('id'),
                'version': unit.get('version', 1),
                'status': unit.get('status', 'active'),
            }
            provenance.append(item)

        logger.debug('Built provenance for %d units', len(provenance))
        return provenance

    def format_citation(
        self,
        evidence: Dict[str, Any],
        source_title: str,
    ) -> str:
        """
        Format a human-readable citation string.

        Examples
        --------
        Video : "Source: Lecture 3, 14:32 [ASR, confidence: 0.91]"
        PDF   : "Source: textbook.pdf, page 47"
        PPT   : "Source: slides.pptx, slide 12"
        """
        modality = evidence.get('modality', 'unknown').upper()
        confidence = evidence.get('confidence', 0.0)
        ts_start = evidence.get('timestamp_start')
        ts_end = evidence.get('timestamp_end')
        page = evidence.get('page')
        slide = evidence.get('slide')

        if ts_start is not None:
            ts_str = _format_timestamp(ts_start)
            if ts_end is not None:
                ts_str += f'–{_format_timestamp(ts_end)}'
            return (
                f'Source: {source_title}, {ts_str} '
                f'[{modality}, confidence: {confidence:.2f}]'
            )
        elif slide is not None:
            return f'Source: {source_title}, slide {slide}'
        elif page is not None:
            return f'Source: {source_title}, page {page}'
        else:
            return f'Source: {source_title} [{modality}]'

    def build_citation_list(
        self,
        evidence_list: List[Dict[str, Any]],
        source_title: str,
    ) -> List[str]:
        """Return a list of formatted citation strings for all evidence items."""
        return [self.format_citation(e, source_title) for e in evidence_list]
