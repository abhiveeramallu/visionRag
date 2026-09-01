"""
Summary, Quiz, Flashcard, and Notes generation for VisionRAG-X.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.generation.llm import friendly_llm_error

logger = logging.getLogger(__name__)


def _fmt_ts(seconds: Optional[float]) -> str:
    if seconds is None:
        return ''
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f'{h:02d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


def _units_to_text(units: List[Dict[str, Any]], max_chars: int = 8000) -> str:
    """Combine knowledge unit content into a single text block for LLM context."""
    parts = []
    total = 0
    for u in units:
        if u.get('status') == 'superseded':
            continue  # skip outdated knowledge
        content = u.get('content', '').strip()
        if not content:
            continue
        chunk = f'[{u.get("modality", "text").upper()}] {content}'
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return '\n\n'.join(parts)


# ---------------------------------------------------------------------------
# Summary Generator
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM = (
    'You are VisionRAG-X, an educational assistant. '
    'Generate clear, well-structured summaries of educational content. '
    'Cite timestamps or page numbers where available. '
    'Do not invent information not present in the provided content.'
)


class SummaryGenerator:
    def __init__(self, llm: Any):
        self.llm = llm

    async def generate_overall(
        self,
        units: List[Dict[str, Any]],
        source_title: str,
    ) -> Dict[str, Any]:
        context = _units_to_text(units)
        prompt = (
            f'Source: "{source_title}"\n\n'
            f'CONTENT:\n{context}\n\n'
            'Write a comprehensive overall summary of this educational material. '
            'Include key concepts, main topics, and important conclusions. '
            'Format with clear sections.'
        )
        error = None
        try:
            content = await self.llm.complete(SUMMARY_SYSTEM, prompt, temperature=0.3, max_tokens=1200)
        except Exception as e:
            logger.warning('Summary generation failed: %s', e)
            error = friendly_llm_error(e)
            content = context[:2000]
        return {
            'source_id': '',
            'summary_type': 'overall',
            'content': content,
            'sections': [],
            'error': error,
            'generated_at': datetime.utcnow().isoformat(),
        }

    async def generate_topic(
        self,
        units: List[Dict[str, Any]],
        topic: str,
        source_title: str,
    ) -> Dict[str, Any]:
        # Filter units relevant to the topic
        topic_lower = topic.lower()
        relevant = [
            u for u in units
            if topic_lower in u.get('content', '').lower()
            or topic_lower in u.get('concept', '').lower()
        ] or units  # fall back to all units if no match
        context = _units_to_text(relevant)
        prompt = (
            f'Source: "{source_title}"\n'
            f'Topic: {topic}\n\n'
            f'CONTENT:\n{context}\n\n'
            f'Write a focused summary about "{topic}" based on this content. '
            'Include relevant examples, definitions, and key points.'
        )
        error = None
        try:
            content = await self.llm.complete(SUMMARY_SYSTEM, prompt, temperature=0.3, max_tokens=1000)
        except Exception as e:
            logger.warning('Topic summary generation failed: %s', e)
            error = friendly_llm_error(e)
            content = context[:2000]
        return {
            'source_id': '',
            'summary_type': 'topic',
            'content': content,
            'sections': [],
            'error': error,
            'generated_at': datetime.utcnow().isoformat(),
        }

    async def generate_timestamped(
        self,
        windows: List[Dict[str, Any]],
        source_title: str,
    ) -> Dict[str, Any]:
        sections = []
        # Group windows into ~5-minute blocks for readable sections
        block_size = 20  # windows (15s each = 5 minutes)
        for i in range(0, len(windows), block_size):
            block = windows[i: i + block_size]
            if not block:
                continue
            ts_start = block[0].get('window_start', 0)
            ts_end = block[-1].get('window_end', ts_start + 300)

            # Combine text from this block
            texts = []
            for w in block:
                for seg in w.get('asr_segments', []):
                    texts.append(seg.get('text', ''))
            combined = ' '.join(texts).strip()
            if not combined:
                continue

            prompt = (
                f'Source: "{source_title}" — Section {_fmt_ts(ts_start)}–{_fmt_ts(ts_end)}\n\n'
                f'TRANSCRIPT:\n{combined[:2000]}\n\n'
                'Write a 2–3 sentence summary of this section. '
                'Be concise and focus on the main topic covered.'
            )
            try:
                section_content = await self.llm.complete(
                    SUMMARY_SYSTEM, prompt, temperature=0.3, max_tokens=200
                )
            except Exception as e:
                section_content = f'[Summary generation failed: {e}]'

            sections.append({
                'title': f'{_fmt_ts(ts_start)} – {_fmt_ts(ts_end)}',
                'content': section_content,
                'timestamp_start': ts_start,
                'timestamp_end': ts_end,
                'page': None,
            })

        full_content = '\n\n'.join(
            f'**{s["title"]}**\n{s["content"]}' for s in sections
        )
        return {
            'source_id': '',
            'summary_type': 'timestamped',
            'content': full_content,
            'sections': sections,
            'generated_at': datetime.utcnow().isoformat(),
        }


# ---------------------------------------------------------------------------
# Quiz Generator
# ---------------------------------------------------------------------------

QUIZ_SYSTEM = (
    'You are VisionRAG-X, an educational assessment generator. '
    'Generate quiz questions ONLY from the provided content. '
    'Never invent facts. Always include a correct answer and a brief explanation. '
    'Respond ONLY with valid JSON — no extra text before or after the JSON.'
)


class QuizGenerator:
    def __init__(self, llm: Any):
        self.llm = llm

    def _difficulty_instruction(self, difficulty: str) -> str:
        return {
            'easy': 'Questions should test basic recall and simple understanding.',
            'medium': 'Questions should require understanding of concepts and their relationships.',
            'hard': 'Questions should require deep analysis, application, or synthesis.',
        }.get(difficulty, 'Medium difficulty.')

    def _build_prompt(
        self,
        context: str,
        quiz_type: str,
        difficulty: str,
        num_questions: int,
        topic: Optional[str],
        source_title: str,
    ) -> str:
        type_instructions = {
            'mcq': (
                f'Generate {num_questions} multiple-choice questions. '
                'Each question must have exactly 4 options (A, B, C, D) and one correct answer. '
                'JSON format: {"questions": [{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], '
                '"answer": "A) ...", "explanation": "..."}]}'
            ),
            'true_false': (
                f'Generate {num_questions} true/false questions. '
                'JSON format: {"questions": [{"question": "...", "options": ["True", "False"], '
                '"answer": "True" or "False", "explanation": "..."}]}'
            ),
            'fill_blank': (
                f'Generate {num_questions} fill-in-the-blank questions. Use ___ for the blank. '
                'JSON format: {"questions": [{"question": "...", "options": null, "answer": "...", "explanation": "..."}]}'
            ),
            'short_answer': (
                f'Generate {num_questions} short-answer questions. '
                'JSON format: {"questions": [{"question": "...", "options": null, "answer": "...", "explanation": "..."}]}'
            ),
        }
        type_instr = type_instructions.get(quiz_type, type_instructions['mcq'])
        topic_note = f'Focus on the topic: {topic}.' if topic else ''

        return (
            f'Source: "{source_title}"\n'
            f'{topic_note}\n'
            f'Difficulty: {self._difficulty_instruction(difficulty)}\n\n'
            f'CONTENT:\n{context}\n\n'
            f'{type_instr}\n'
            'Return ONLY that JSON object, nothing else.'
        )

    async def generate(
        self,
        units: List[Dict[str, Any]],
        quiz_type: str,
        difficulty: str,
        num_questions: int,
        topic: Optional[str],
        source_title: str,
    ) -> Dict[str, Any]:
        context = _units_to_text(units, max_chars=6000)
        prompt = self._build_prompt(context, quiz_type, difficulty, num_questions, topic, source_title)

        questions = []
        try:
            raw = await self.llm.complete(QUIZ_SYSTEM, prompt, temperature=0.4, max_tokens=3000, json_mode=True)
        except Exception as e:
            logger.warning('Quiz generation failed: %s', e)
            return {
                'source_id': '',
                'questions': [],
                'topic': topic,
                'difficulty': difficulty,
                'error': friendly_llm_error(e),
                'generated_at': datetime.utcnow().isoformat(),
            }

        try:
            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0]
            parsed = json.loads(cleaned)
            # Accept both {"questions": [...]} (what we ask for — required for
            # OpenAI's strict JSON mode) and a bare [...] (what some models,
            # local ones especially, still produce despite the instruction).
            question_list = parsed.get('questions', []) if isinstance(parsed, dict) else parsed
            for i, q in enumerate(question_list[:num_questions]):
                questions.append({
                    'question_id': str(uuid.uuid4()),
                    'question': q.get('question', ''),
                    'question_type': quiz_type,
                    'options': q.get('options'),
                    'answer': q.get('answer', ''),
                    'explanation': q.get('explanation', ''),
                    'difficulty': difficulty,
                    'source_evidence': None,
                })
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning('Quiz JSON parse failed: %s\nRaw: %s', e, raw[:300])
            return {
                'source_id': '',
                'questions': [],
                'topic': topic,
                'difficulty': difficulty,
                'error': 'The AI response could not be understood — please try generating again.',
                'generated_at': datetime.utcnow().isoformat(),
            }

        return {
            'source_id': '',
            'questions': questions,
            'topic': topic,
            'difficulty': difficulty,
            'error': None,
            'generated_at': datetime.utcnow().isoformat(),
        }


# ---------------------------------------------------------------------------
# Flashcard Generator
# ---------------------------------------------------------------------------

FLASHCARD_SYSTEM = (
    'You are VisionRAG-X, an educational flashcard generator. '
    'Create question-answer flashcard pairs from educational content. '
    'Prefer verified and important concepts. '
    'Be concise: front = 1 clear question, back = 1–2 sentence answer. '
    'Respond ONLY with valid JSON — no extra text.'
)


class FlashcardGenerator:
    def __init__(self, llm: Any):
        self.llm = llm

    async def generate(
        self,
        units: List[Dict[str, Any]],
        num_cards: int,
        topic: Optional[str],
        source_title: str,
    ) -> Dict[str, Any]:
        # Prefer verified and active units
        ordered = sorted(
            units,
            key=lambda u: (
                {'verified': 0, 'active': 1, 'disputed': 2, 'superseded': 3}.get(u.get('status', 'active'), 1),
                -u.get('confidence', 0.5),
            ),
        )
        context = _units_to_text(ordered, max_chars=6000)
        topic_note = f'Focus on: {topic}.' if topic else ''

        prompt = (
            f'Source: "{source_title}"\n{topic_note}\n\n'
            f'CONTENT:\n{context}\n\n'
            f'Generate {num_cards} flashcard pairs. '
            'JSON format: {"cards": [{"front": "Question?", "back": "Answer.", "concept": "Topic name"}]}\n'
            'Return ONLY that JSON object.'
        )

        cards = []
        try:
            raw = await self.llm.complete(FLASHCARD_SYSTEM, prompt, temperature=0.35, max_tokens=2500, json_mode=True)
        except Exception as e:
            logger.warning('Flashcard generation failed: %s', e)
            return {
                'source_id': '',
                'cards': [],
                'topic': topic,
                'error': friendly_llm_error(e),
                'generated_at': datetime.utcnow().isoformat(),
            }

        try:
            cleaned = raw.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0]
            parsed = json.loads(cleaned)
            card_list = parsed.get('cards', []) if isinstance(parsed, dict) else parsed
            for c in card_list[:num_cards]:
                cards.append({
                    'card_id': str(uuid.uuid4()),
                    'front': c.get('front', ''),
                    'back': c.get('back', ''),
                    'concept': c.get('concept', ''),
                    'source_evidence': None,
                    'confidence': 0.7,
                })
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning('Flashcard JSON parse failed: %s', e)
            return {
                'source_id': '',
                'cards': [],
                'topic': topic,
                'error': 'The AI response could not be understood — please try generating again.',
                'generated_at': datetime.utcnow().isoformat(),
            }

        return {
            'source_id': '',
            'cards': cards,
            'topic': topic,
            'error': None,
            'generated_at': datetime.utcnow().isoformat(),
        }


# ---------------------------------------------------------------------------
# Notes Generator
# ---------------------------------------------------------------------------

NOTES_SYSTEM = (
    'You are VisionRAG-X, an educational notes generator. '
    'Generate structured study notes from educational content. '
    'Do not invent information. Use markdown formatting.'
)


class NotesGenerator:
    def __init__(self, llm: Any):
        self.llm = llm

    async def generate(
        self,
        units: List[Dict[str, Any]],
        notes_type: str,
        topic: Optional[str],
        source_title: str,
    ) -> Dict[str, Any]:
        context = _units_to_text(units)
        topic_note = f'Focus on: {topic}.' if topic else ''

        style = {
            'concise': 'Write concise bullet-point notes. 1–2 lines per point. No preamble.',
            'detailed': (
                'Write detailed notes with explanations, examples, and context. '
                'Use headings, subheadings, and bullet points.'
            ),
            'revision': (
                'Write revision-style notes: key terms in bold, definitions, formulas, '
                'and 3–5 example questions at the end.'
            ),
        }.get(notes_type, 'Write concise notes.')

        prompt = (
            f'Source: "{source_title}"\n{topic_note}\n\n'
            f'CONTENT:\n{context}\n\n'
            f'{style}'
        )
        error = None
        try:
            content = await self.llm.complete(NOTES_SYSTEM, prompt, temperature=0.25, max_tokens=2000)
        except Exception as e:
            logger.warning('Notes generation failed: %s', e)
            error = friendly_llm_error(e)
            content = context[:2000]

        return {
            'source_id': '',
            'notes_type': notes_type,
            'content': content,
            'sections': [],
            'error': error,
            'generated_at': datetime.utcnow().isoformat(),
        }
