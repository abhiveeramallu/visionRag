"""
Correction / version-chain detection for VisionRAG-X's Verified Knowledge
Evolution Graph (VKEG).

EXPERIMENTAL: deterministic rule-based heuristics — not a learned model.
Links a newly extracted knowledge unit to an earlier one it corrects by
combining (a) explicit correction language and (b) topical keyword overlap
with recently seen concepts for the same source. Both signals are required
so a merely *related* statement is never mistaken for a correction.
"""
import re
from typing import Optional, Set

# Deliberately excludes bare "correction"/"needs correction" — those show up
# in forward-looking or descriptive notes ("this slide needs correction next
# lecture") that don't themselves correct anything, which produced false
# positives. Every phrase here specifically asserts *this* statement is fixing
# an earlier one.
CORRECTION_PHRASES = [
    "sorry", "i made a mistake", "that's incorrect", "that is incorrect",
    "let me correct", "the actual answer is", "the actual correct",
    "i meant to say", "i meant", "correction:", "to correct that",
    "my apologies", "actually, it's", "actually it's", "not quite right",
    "let me fix that", "scratch that", "i misspoke", "that was wrong",
    "let me restate", "should be corrected to", "was an error",
]

_STOPWORDS = {
    'this', 'that', 'with', 'from', 'have', 'been', 'were', 'their',
    'about', 'which', 'there', 'these', 'those', 'when', 'where', 'what',
    'will', 'would', 'could', 'should', 'into', 'each', 'other', 'more',
    'most', 'some', 'such', 'than', 'then', 'them', 'they', 'also', 'because',
    'source', 'page', 'course', 'sample',
}

_WORD_RE = re.compile(r"[a-zA-Z']{4,}")


def detect_correction_phrase(text: str) -> Optional[str]:
    """Return the first correction phrase found in *text*, if any."""
    lowered = text.lower()
    for phrase in CORRECTION_PHRASES:
        if phrase in lowered:
            return phrase
    return None


def content_keywords(text: str) -> Set[str]:
    """Rough topical fingerprint: lowercase words >=4 chars, stopwords removed."""
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def keyword_overlap(a: Set[str], b: Set[str]) -> float:
    """
    Overlap coefficient (intersection / smaller set size) between two keyword
    sets. Deliberately not Jaccard: two genuinely-the-same-topic passages of
    very different length (e.g. a one-line correction vs. a full paragraph)
    share only a handful of words in common, so a union-based ratio is almost
    always too small to cross any reasonable threshold — the smaller side is
    the more informative denominator here.
    """
    if not a or not b:
        return 0.0
    smaller = min(len(a), len(b))
    return len(a & b) / smaller if smaller else 0.0
