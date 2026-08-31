"""
Formula extraction module for VisionRAG-X.

Detects mathematical formulae and notation in text segments using
regex-based heuristics. Intended as a lightweight pre-filter before
a dedicated math-rendering or CAS pipeline.
"""

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Pattern library
# ------------------------------------------------------------------ #

_RAW_PATTERNS = [
    # Big-O / algorithmic complexity
    r"O\s*\(\s*[nNkKm\d\w\^\*\s\+\-\/log]+\s*\)",
    r"\bTheta\s*\(|\bOmega\s*\(",

    # Fractions (LaTeX and plain-text)
    r"\\frac\s*\{[^}]+\}\s*\{[^}]+\}",
    r"\d+\s*/\s*\d+",                            # e.g. 3/4

    # Integrals
    r"\\int(?:_\{[^}]*\})?\s*(?:\^?\{[^}]*\})?",
    r"\bintegral\b",

    # Summations
    r"\\sum(?:_\{[^}]*\})?\s*(?:\^?\{[^}]*\})?",
    r"\bsummation\b",
    r"Σ",

    # Limits, derivatives
    r"\\lim\b",
    r"\blimit\s+as\b",
    r"\bderivative\b",
    r"d/d[xyt]",

    # Square root / logarithm / natural log
    r"\\sqrt\s*\{[^}]+\}",
    r"\bsqrt\s*\(",
    r"\blog\s*\(",
    r"\bln\s*\(",
    r"log_\{?[^}]+\}?",

    # Nabla / del operator
    r"∇|\\nabla\b",

    # Delta (capital and lower)
    r"\\[Dd]elta\b",
    r"Δ|δ",

    # Infinity
    r"\\infty\b",
    r"∞",

    # Matrix / vector notation
    r"\\begin\{(?:pmatrix|bmatrix|matrix|vmatrix)\}",
    r"\bmatrix\b|\bvector\b",

    # Generic LaTeX commands
    r"\\(?:frac|int|sum|prod|lim|sqrt|partial|nabla|alpha|beta|gamma|delta|epsilon|"
    r"zeta|eta|theta|iota|kappa|lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega)\b",

    # Greek letter names (English)
    r"\b(?:alpha|beta|gamma|delta|epsilon|theta|lambda|mu|sigma|omega|phi|psi|xi|eta|"
    r"kappa|rho|tau|upsilon|chi|zeta|iota|nu|omicron|pi)\b",

    # Equations: contains = and at least one operator/variable
    r"[A-Za-z\d]+\s*=\s*[A-Za-z\d\+\-\*\/\^\(\)\s]+",

    # Exponents / superscripts
    r"\w+\^\w+",
    r"\w+\*\*\d+",

    # Powers of 2 / 10 (common in CS lectures)
    r"2\^[nN\d]+",
    r"10\^[nN\d]+",
]

FORMULA_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE | re.MULTILINE)
    for p in _RAW_PATTERNS
]


# ------------------------------------------------------------------ #
# FormulaExtractor
# ------------------------------------------------------------------ #

class FormulaExtractor:
    """
    Lightweight formula detector using compiled regex patterns.

    Not a full mathematical parser — use a dedicated CAS or LaTeX
    renderer for downstream rendering or evaluation.
    """

    def _is_formula(self, text: str) -> bool:
        """
        Return True if *text* contains at least one formula-like pattern.

        Parameters
        ----------
        text:
            Plain text to test.
        """
        if not text or not text.strip():
            return False
        return any(pattern.search(text) for pattern in FORMULA_PATTERNS)

    def extract_from_text(self, text: str) -> List[str]:
        """
        Return all formula substrings found in *text*.

        Each matched pattern contributes its match to the result list.
        Duplicates are preserved; the caller may deduplicate if needed.

        Parameters
        ----------
        text:
            Plain text to search.

        Returns
        -------
        List of matched formula strings (may be empty).
        """
        found: List[str] = []
        for pattern in FORMULA_PATTERNS:
            for match in pattern.finditer(text):
                found.append(match.group(0).strip())
        return found

    async def extract_from_segments(self, segments: List[dict]) -> List[dict]:
        """
        Filter a list of OCR/ASR segments, returning only those that
        contain detectable formula content.

        Each returned segment has ``modality='formula'`` and a
        ``formula_matches`` key listing the matched substrings.

        Parameters
        ----------
        segments:
            List of RawSegment-compatible dicts from OCR or ASR.

        Returns
        -------
        Filtered list of dicts with modality='formula'.
        """
        formula_segments: List[dict] = []
        for seg in segments:
            text = seg.get("text", "")
            if not self._is_formula(text):
                continue

            matches = self.extract_from_text(text)
            new_seg = dict(seg)
            new_seg["modality"] = "formula"
            new_seg["raw_output"] = {
                **seg.get("raw_output", {}),
                "formula_matches": matches,
            }
            formula_segments.append(new_seg)

        logger.debug(
            "FormulaExtractor: %d/%d segments identified as formulas",
            len(formula_segments),
            len(segments),
        )
        return formula_segments
