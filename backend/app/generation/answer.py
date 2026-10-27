"""
Provenance-aware answer generation for VisionRAG-X.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def _fmt_ts(seconds: Optional[float]) -> str:
    if seconds is None:
        return ''
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f'{h:02d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


ANSWER_SYSTEM_PROMPT = """You are VisionRAG-X, an authoritative educational assistant that helps students learn from multimodal lecture content.

STRICT RESEARCH INTEGRITY RULES — follow all of them:
1. Answer ONLY from the provided EVIDENCE. Do not add unsupported facts, external training knowledge, or hallucinate.
2. If evidence contains a SUPERSEDED claim that was later corrected, cite the correction and explicitly state: "The instructor initially stated X, but this was corrected to Y."
3. If evidence is conflicting, explicitly state: "The sources disagree on this point" and describe both claims.
4. Cite your evidence inline using the bracketed evidence index (e.g. [1], [2]) or exact timestamp/page (e.g. at 14:32, Page 6).
5. NEVER invent bracket indices, page numbers, timestamps, or quotations not present in the evidence. Only cite indices that appear in === EVIDENCE ===.
6. If the provided evidence is completely insufficient or does not address the question, state: "The provided educational sources do not establish this answer; insufficient evidence."
7. Keep answers concise, factual, and complete. Use bullet points where appropriate.
"""


def validate_citations(
    answer: str,
    evidence: List[Dict[str, Any]],
) -> Tuple[str, List[int], List[int]]:
    """
    Validate inline citations emitted by the LLM against the actual retrieved evidence.

    Returns:
        (sanitized_answer, valid_indices, invalid_indices)
    """
    if not evidence or not answer:
        return answer, [], []

    bracket_pattern = re.compile(r'\[(\d+)\]')
    found_matches = [int(m) for m in bracket_pattern.findall(answer)]
    valid_indices: List[int] = []
    invalid_indices: List[int] = []

    num_evidence = len(evidence)
    for idx in found_matches:
        if 1 <= idx <= num_evidence:
            if idx not in valid_indices:
                valid_indices.append(idx)
        else:
            if idx not in invalid_indices:
                invalid_indices.append(idx)

    # If the model emitted hallucinated citation numbers, sanitize them out
    sanitized_answer = answer
    if invalid_indices:
        logger.warning(
            "Model emitted invalid citation index(es) %s (evidence count: %d). Sanitizing.",
            invalid_indices, num_evidence
        )
        for inv in invalid_indices:
            sanitized_answer = re.sub(rf'\[{inv}\]', '', sanitized_answer)
        sanitized_answer = re.sub(r'  +', ' ', sanitized_answer).strip()

    return sanitized_answer, valid_indices, invalid_indices


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
                if c.get('is_genuine_conflict') is False or c.get('verification_status') == 'false_positive':
                    continue
                if c.get('is_genuine_conflict') is True:
                    prefix = f'⚠️ Verified Contradiction ({c.get("type", "unknown")}, severity: {c.get("severity", "?")}, status: {c.get("status", "unresolved")})'
                else:
                    prefix = f'ℹ️ Candidate Discrepancy (unverified candidate, type: {c.get("type", "unknown")}, severity: {c.get("severity", "?")})'
                lines.append(
                    f'{prefix}\n'
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
        abstain: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate an answer grounded in the provided evidence.

        Returns
        -------
        dict:
            answer         : str
            evidence_used  : List[dict]
            confidence     : float
            abstained      : bool
        """
        if abstain or not evidence:
            return {
                'answer': 'The provided educational sources do not establish this answer; insufficient evidence.',
                'evidence_used': [],
                'confidence': 0.0,
                'abstained': True,
                'valid_citation_indices': [],
                'invalid_citation_indices': [],
            }

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

        sanitized_answer, valid_indices, invalid_indices = validate_citations(answer, evidence)

        # Map valid bracket indices to evidence items
        cited_evidence = [evidence[i - 1] for i in valid_indices] if valid_indices else evidence[:3]

        confidence = self._estimate_confidence(evidence)
        return {
            'answer': sanitized_answer,
            'evidence_used': evidence,
            'cited_evidence': cited_evidence,
            'valid_citation_indices': valid_indices,
            'invalid_citation_indices': invalid_indices,
            'confidence': confidence,
            'abstained': False,
        }
