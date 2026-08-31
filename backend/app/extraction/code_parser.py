import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class CodeParser:
    """
    Extracts code blocks from text segments using heuristic pattern matching.
    Detects: Python, JavaScript, Java, C/C++, SQL, bash.
    """
    
    LANGUAGE_PATTERNS = {
        'python': [
            r'def\s+\w+\s*\(',
            r'import\s+\w+',
            r'from\s+\w+\s+import',
            r'class\s+\w+[:(]',
            r'if\s+__name__\s*==',
            r'print\s*\(',
            r'\bfor\b.+\bin\b',
            r'lambda\s+\w+:',
        ],
        'javascript': [
            r'function\s+\w+\s*\(',
            r'const\s+\w+\s*=',
            r'let\s+\w+\s*=',
            r'var\s+\w+\s*=',
            r'=>\s*{',
            r'console\.log\(',
            r'\$\(\s*[\'"]',
            r'document\.getElementById',
        ],
        'sql': [
            r'\bSELECT\b.*\bFROM\b',
            r'\bINSERT\s+INTO\b',
            r'\bUPDATE\b.*\bSET\b',
            r'\bDELETE\s+FROM\b',
            r'\bCREATE\s+TABLE\b',
            r'\bJOIN\b.*\bON\b',
            r'\bWHERE\b',
        ],
        'bash': [
            r'^#!.*sh',
            r'\$\{?\w+\}?',
            r'\bsudo\b',
            r'\bpip\b',
            r'\bapt-get\b',
            r'\becho\b',
            r'\|\s*grep\b',
        ],
        'java': [
            r'public\s+class\s+\w+',
            r'public\s+static\s+void\s+main',
            r'import\s+java\.',
            r'System\.out\.print',
            r'\bvoid\b.*\(.*\)\s*{',
            r'@Override',
        ],
        'cpp': [
            r'#include\s*<',
            r'int\s+main\s*\(',
            r'std::',
            r'cout\s*<<',
            r'cin\s*>>',
            r'\btemplate\b',
            r'nullptr',
        ],
    }
    
    def __init__(self):
        self._compiled = {
            lang: [re.compile(p, re.IGNORECASE | re.MULTILINE) 
                   for p in patterns]
            for lang, patterns in self.LANGUAGE_PATTERNS.items()
        }
    
    def detect_language(self, text: str) -> Optional[tuple]:
        """Returns (language, confidence) or None."""
        scores = {}
        for lang, patterns in self._compiled.items():
            matches = sum(1 for p in patterns if p.search(text))
            if matches > 0:
                scores[lang] = matches / len(patterns)
        if not scores:
            return None
        best_lang = max(scores, key=scores.get)
        return (best_lang, scores[best_lang])
    
    def _looks_like_code(self, text: str) -> bool:
        """Heuristic: does this text look like code?"""
        indicators = [
            len(re.findall(r'[{}();]', text)) >= 3,
            bool(re.search(r'\bdef\b|\bfunction\b|\bclass\b|\bvoid\b', text)),
            bool(re.search(r'[A-Za-z]+\(.*\)', text)),
            self.detect_language(text) is not None,
        ]
        return sum(indicators) >= 2
    
    def extract_code_blocks(self, text: str) -> List[dict]:
        """Extract code blocks from mixed text."""
        blocks = []
        # Find fenced code blocks (```language ... ```)
        fenced = re.finditer(r'```(\w+)?\n?(.*?)```', text, re.DOTALL)
        for match in fenced:
            lang = match.group(1) or 'unknown'
            code = match.group(2).strip()
            blocks.append({'code': code, 'language': lang, 'confidence': 0.95})
        
        if not blocks and self._looks_like_code(text):
            lang_result = self.detect_language(text)
            if lang_result:
                lang, conf = lang_result
                blocks.append({'code': text, 'language': lang, 'confidence': conf})
        
        return blocks
    
    def process_segments(self, segments: List[dict]) -> List[dict]:
        """Returns segments with modality='code' for detected code content."""
        code_segments = []
        for seg in segments:
            text = seg.get('text', '')
            blocks = self.extract_code_blocks(text)
            for block in blocks:
                new_seg = dict(seg)
                new_seg['modality'] = 'code'
                new_seg['text'] = block['code']
                new_seg['raw_output'] = {
                    **seg.get('raw_output', {}),
                    'language': block['language'],
                    'code_confidence': block['confidence']
                }
                code_segments.append(new_seg)
        return code_segments
