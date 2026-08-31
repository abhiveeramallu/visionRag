"""
Pure-Python dataclasses representing the knowledge extraction pipeline's
intermediate and final data structures.

These are transport objects – they are NOT ORM models.  The pipeline
produces these objects, which are then persisted to PostgreSQL and Qdrant
by the ingestion services.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# RawSegment
# ---------------------------------------------------------------------------

@dataclass
class RawSegment:
    """
    A single raw output segment produced by one extraction modality.

    Attributes
    ----------
    text:
        The extracted text content (ASR transcript, OCR text, vision caption,
        formula string, code block, etc.).
    modality:
        One of: asr | ocr | vision | formula | code.
    source_id:
        ID of the parent Source record.
    timestamp_start:
        Start time in seconds (video/audio segments only).
    timestamp_end:
        End time in seconds (video/audio segments only).
    page:
        1-indexed page number (PDF/PPT sources only).
    slide:
        1-indexed slide number (PPT sources only).
    confidence:
        Extraction confidence in [0, 1].
    raw_output:
        The original, un-normalised extraction output dict (e.g. WhisperX
        word-level segment, PaddleOCR box dict, etc.).
    """

    text: str
    modality: str
    source_id: str
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    page: Optional[int] = None
    slide: Optional[int] = None
    confidence: float = 1.0
    raw_output: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "text": self.text,
            "modality": self.modality,
            "source_id": self.source_id,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "page": self.page,
            "slide": self.slide,
            "confidence": self.confidence,
        }

    def format_citation(self) -> str:
        """Return a human-readable citation string for this segment."""
        parts = [f"[{self.modality.upper()}]"]
        if self.timestamp_start is not None:
            ts = f"{self.timestamp_start:.1f}s"
            if self.timestamp_end is not None:
                ts += f"–{self.timestamp_end:.1f}s"
            parts.append(ts)
        if self.page is not None:
            parts.append(f"p.{self.page}")
        if self.slide is not None:
            parts.append(f"slide {self.slide}")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# AlignedWindow
# ---------------------------------------------------------------------------

@dataclass
class AlignedWindow:
    """
    A time- or page-aligned window that groups raw segments from all
    modalities that overlap the same temporal or spatial region.

    This is the unit of cross-modal alignment used during conflict detection
    and knowledge-unit extraction.
    """

    window_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    window_start: Optional[float] = None   # seconds
    window_end: Optional[float] = None     # seconds
    page: Optional[int] = None
    slide: Optional[int] = None

    # Per-modality segment lists
    asr_segments: List[RawSegment] = field(default_factory=list)
    ocr_segments: List[RawSegment] = field(default_factory=list)
    vision_segments: List[RawSegment] = field(default_factory=list)
    formula_segments: List[RawSegment] = field(default_factory=list)
    code_segments: List[RawSegment] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def all_segments(self) -> List[RawSegment]:
        """Return all segments from all modalities in a flat list."""
        return (
            self.asr_segments
            + self.ocr_segments
            + self.vision_segments
            + self.formula_segments
            + self.code_segments
        )

    @property
    def is_empty(self) -> bool:
        """True when no segments have been added to any modality."""
        return len(self.all_segments) == 0

    @property
    def primary_text(self) -> str:
        """
        Return the concatenated ASR transcript for this window.

        Falls back to OCR text if no ASR segments are present, and to an
        empty string if neither is available.
        """
        if self.asr_segments:
            return " ".join(s.text for s in self.asr_segments).strip()
        if self.ocr_segments:
            return " ".join(s.text for s in self.ocr_segments).strip()
        return ""


# ---------------------------------------------------------------------------
# ProcessedKnowledgeUnit
# ---------------------------------------------------------------------------

@dataclass
class ProcessedKnowledgeUnit:
    """
    A fully processed and versioned knowledge atom ready for storage.

    Produced by the knowledge extraction stage after cross-modal alignment,
    conflict detection, and concept labelling.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    concept: str = ""            # Short label, e.g. "Newton's First Law"
    content: str = ""            # Full explanation / text
    modality: str = ""           # Dominant modality: asr|ocr|vision|formula|code
    source_id: str = ""

    # Provenance
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    page: Optional[int] = None
    slide: Optional[int] = None

    # Quality
    confidence: float = 1.0

    # Supporting evidence
    evidence: List[RawSegment] = field(default_factory=list)

    # Versioning / lifecycle
    status: str = "active"       # active | superseded | disputed | verified
    version: int = 1
    previous_version_id: Optional[str] = None
    correction_reason: Optional[str] = None

    # Vector store reference (populated after embedding & upsert)
    embedding: Optional[List[float]] = None
    embedding_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Methods
    # ------------------------------------------------------------------

    def to_evidence_item(self) -> Dict[str, Any]:
        """
        Serialise to a dict matching the EvidenceItem Pydantic schema,
        suitable for inclusion in QueryResponse / KnowledgeUnitResponse.
        """
        return {
            "text": self.content,
            "source_id": self.source_id,
            "modality": self.modality,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "page": self.page,
            "slide": self.slide,
            "confidence": self.confidence,
            "knowledge_unit_id": self.id,
            "version": self.version,
            "status": self.status,
        }

    def format_citation(self) -> str:
        """Human-readable citation string for this knowledge unit."""
        parts = [f"[{self.modality.upper()}]", f"(v{self.version})"]
        if self.timestamp_start is not None:
            ts = f"{self.timestamp_start:.1f}s"
            if self.timestamp_end is not None:
                ts += f"–{self.timestamp_end:.1f}s"
            parts.append(ts)
        if self.page is not None:
            parts.append(f"p.{self.page}")
        if self.slide is not None:
            parts.append(f"slide {self.slide}")
        return " ".join(parts)

    @property
    def is_active(self) -> bool:
        """True if this unit is in an 'active' or 'verified' lifecycle state."""
        return self.status in ("active", "verified")
