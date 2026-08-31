"""
Provenance-aware answer generation for VisionRAG-X.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _fmt_ts(seconds: Optional[float]) -> str:
    if seconds is None:
        return ''
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f'{h:02d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


ANSWER_SYSTEM_PROMPT = """You are VisionRAG-X, an educational assistant that helps students learn from multimodal content.

STRICT RULES — follow all of them:
1. Answer ONLY from the provided EVIDENCE. Do not add unsupported facts or hallucinate.
2. If evidence is conflicting, explicitly state: "The sources disagree on this point."
3. Cite your sources inline. For video: use timestamp (e.g., "at 14:32"). For documents: cite page/slide number.
4. If a knowledge unit is marked as SUPERSEDED, say: "The instructor initially stated X (at T1) and later corrected this to Y (at T2)."
5. When uncertain, prefix with: "Based on the available evidence..."
6. Never invent timestamps, page numbers, or facts not present in the evidence.
7. Keep answers concise but complete. Use bullet points for lists.
8. End with a brief source summary if multiple sources are used.
"""


class AnswerGenerator:
    """
    Generates provenance-aware answers from retrieved evidence.

    The LLM is instructed to cite every claim and flag conflicts/corrections.
    """

    def __init__(self, llm: Any, provenance: Any):
        self.llm = llm
        self.provenance = provenance

    def _build_context(
        self,
        evidence: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
    ) -> str:
        """Format evidence items and conflicts into an LLM-readable context string."""
        lines = ['=== EVIDENCE ===\n']
        for i, item in enumerate(evidence, 1):
            modality = item.get('modality', 'unknown').upper()
            ts_start = item.get('timestamp_start')
            ts_end = item.get('timestamp_end')
            page = item.get('page')
            slide = item.get('slide')
            confidence = item.get('confidence', 0.5)
            status = item.get('status', 'active')
            content = item.get('text', item.get('content', '')).strip()

            location = ''
            if ts_start is not None:
                location = f'Timestamp: {_fmt_ts(ts_start)}'
                if ts_end is not None:
                    location += f'–{_fmt_ts(ts_end)}'
            elif slide is not None:
                location = f'Slide: {slide}'
            elif page is not None:
                location = f'Page: {page}'

            status_note = ''
            if status == 'superseded':
                status_note = ' ⚠️ [SUPERSEDED — this was later corrected]'
            elif status == 'disputed':
                status_note = ' ⚠️ [DISPUTED — conflicting evidence exists]'

            lines.append(
                f'[{i}] [{modality}]{status_note} {location} (confidence: {confidence:.2f})\n'
                f'{content}\n'
            )

        if conflicts:
            lines.append('\n=== DETECTED CONFLICTS ===\n')
            for c in conflicts:
                lines.append(
                    f'⚠️ Conflict ({c.get("type", "unknown")}, severity: {c.get("severity", "?")})\n'
                    + '\n'.join(f'  - {claim}' for claim in c.get('claims', []))
                    + '\n'
                )

        return '\n'.join(lines)

    def _estimate_confidence(self, evidence: List[Dict[str, Any]]) -> float:
        if not evidence:
            return 0.0
        confs = [float(e.get('confidence', 0.5)) for e in evidence]
        return round(sum(confs) / len(confs), 3)

    async def generate(
        self,
        query: str,
        evidence: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
        source_title: str,
    ) -> Dict[str, Any]:
        """
        Generate an answer grounded in the provided evidence.

        Returns
        -------
        dict:
            answer         : str
            evidence_used  : List[dict]
            confidence     : float
        """
        context = self._build_context(evidence, conflicts)
        user_prompt = (
            f'Source material: "{source_title}"\n\n'
            f'{context}\n\n'
            f'QUESTION: {query}\n\n'
            'Answer the question using only the evidence above. '
            'Cite timestamps or pages for every claim.'
        )

        answer = await self.llm.complete(
            system_prompt=ANSWER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=1500,
        )

        confidence = self._estimate_confidence(evidence)
        return {
            'answer': answer,
            'evidence_used': evidence,
            'confidence': confidence,
        }
