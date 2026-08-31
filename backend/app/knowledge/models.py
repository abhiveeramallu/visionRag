"""
SQLAlchemy ORM models for VisionRAG-X.

Tables
------
sources          – ingested content sources (videos, PDFs, etc.)
processing_jobs  – background ingestion jobs per source
knowledge_units  – extracted, versioned knowledge atoms
evidence         – raw evidence segments backing knowledge units
conflicts        – detected cross-modal contradictions
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.postgres import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

class Source(Base):
    """A single ingested content source."""

    __tablename__ = "sources"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    title: str = Column(String(512), nullable=False)
    source_type: str = Column(String(32), nullable=False)  # pdf | ppt | image | video | audio
    url: Optional[str] = Column(Text, nullable=True)
    file_path: Optional[str] = Column(Text, nullable=True)
    duration: Optional[float] = Column(Float, nullable=True)       # seconds (video/audio)
    num_pages: Optional[int] = Column(Integer, nullable=True)      # PDF/PPT page count
    channel: Optional[str] = Column(String(256), nullable=True)    # YouTube channel
    upload_date: Optional[str] = Column(String(32), nullable=True) # YYYYMMDD string from yt-dlp
    status: str = Column(String(32), nullable=False, default="pending")  # pending|processing|completed|failed
    metadata_: Optional[dict] = Column("metadata", JSON, nullable=True, default=dict)
    created_at: datetime = Column(DateTime, nullable=False, default=_now, server_default=func.now())
    updated_at: datetime = Column(DateTime, nullable=False, default=_now, onupdate=_now, server_default=func.now())

    # Relationships
    processing_jobs = relationship("ProcessingJob", back_populates="source", cascade="all, delete-orphan")
    knowledge_units = relationship("KnowledgeUnit", back_populates="source", cascade="all, delete-orphan")
    conflicts = relationship("Conflict", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Source id={self.id!r} title={self.title!r} type={self.source_type!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# ProcessingJob
# ---------------------------------------------------------------------------

class ProcessingJob(Base):
    """Tracks the lifecycle of a background ingestion pipeline run."""

    __tablename__ = "processing_jobs"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    source_id: str = Column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    status: str = Column(String(32), nullable=False, default="pending")  # pending|processing|completed|failed
    current_step: Optional[str] = Column(String(128), nullable=True)
    progress: float = Column(Float, nullable=False, default=0.0)          # 0.0 – 1.0
    error_message: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_now, server_default=func.now())
    updated_at: datetime = Column(DateTime, nullable=False, default=_now, onupdate=_now, server_default=func.now())

    # Relationships
    source = relationship("Source", back_populates="processing_jobs")

    def __repr__(self) -> str:
        return (
            f"<ProcessingJob id={self.id!r} source_id={self.source_id!r} "
            f"status={self.status!r} progress={self.progress:.0%}>"
        )


# ---------------------------------------------------------------------------
# KnowledgeUnit
# ---------------------------------------------------------------------------

class KnowledgeUnit(Base):
    """
    A single versioned knowledge atom extracted from a source.

    Versioning is a linked-list: previous_version_id -> older KnowledgeUnit.
    """

    __tablename__ = "knowledge_units"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    concept: str = Column(String(512), nullable=False, index=True)
    content: str = Column(Text, nullable=False)
    modality: str = Column(String(32), nullable=False)  # asr|ocr|vision|formula|code
    source_id: str = Column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp_start: Optional[float] = Column(Float, nullable=True)
    timestamp_end: Optional[float] = Column(Float, nullable=True)
    page: Optional[int] = Column(Integer, nullable=True)
    slide: Optional[int] = Column(Integer, nullable=True)
    confidence: float = Column(Float, nullable=False, default=1.0)
    status: str = Column(String(32), nullable=False, default="active")   # active|superseded|disputed|verified
    version: int = Column(Integer, nullable=False, default=1)
    previous_version_id: Optional[str] = Column(
        String(36),
        ForeignKey("knowledge_units.id", ondelete="SET NULL"),
        nullable=True,
    )
    correction_reason: Optional[str] = Column(Text, nullable=True)
    embedding_id: Optional[str] = Column(String(64), nullable=True)  # Qdrant point ID
    created_at: datetime = Column(DateTime, nullable=False, default=_now, server_default=func.now())

    # Relationships
    source = relationship("Source", back_populates="knowledge_units")
    previous_version = relationship("KnowledgeUnit", remote_side="KnowledgeUnit.id", uselist=False)
    evidence_items = relationship("Evidence", back_populates="knowledge_unit", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<KnowledgeUnit id={self.id!r} concept={self.concept!r} "
            f"modality={self.modality!r} status={self.status!r} v={self.version}>"
        )


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class Evidence(Base):
    """
    A raw evidence segment (text span) that supports a KnowledgeUnit.
    """

    __tablename__ = "evidence"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    knowledge_unit_id: str = Column(
        String(36),
        ForeignKey("knowledge_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: str = Column(Text, nullable=False)
    modality: str = Column(String(32), nullable=False)  # asr|ocr|vision|formula|code
    source_id: str = Column(String(36), nullable=False, index=True)
    timestamp_start: Optional[float] = Column(Float, nullable=True)
    timestamp_end: Optional[float] = Column(Float, nullable=True)
    page: Optional[int] = Column(Integer, nullable=True)
    extraction_confidence: float = Column(Float, nullable=False, default=1.0)
    created_at: datetime = Column(DateTime, nullable=False, default=_now, server_default=func.now())

    # Relationships
    knowledge_unit = relationship("KnowledgeUnit", back_populates="evidence_items")

    def __repr__(self) -> str:
        preview = self.text[:60].replace("\n", " ")
        return (
            f"<Evidence id={self.id!r} modality={self.modality!r} "
            f"ku_id={self.knowledge_unit_id!r} text={preview!r}>"
        )


# ---------------------------------------------------------------------------
# Conflict
# ---------------------------------------------------------------------------

class Conflict(Base):
    """
    A detected cross-modal contradiction within a source.
    """

    __tablename__ = "conflicts"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    source_id: str = Column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    conflict_type: str = Column(String(64), nullable=False)  # e.g. asr_vs_ocr, temporal
    modalities: list = Column(JSON, nullable=False, default=list)   # ["asr", "ocr"]
    claims: list = Column(JSON, nullable=False, default=list)        # list of conflicting text strings
    timestamp: Optional[float] = Column(Float, nullable=True)
    page: Optional[int] = Column(Integer, nullable=True)
    severity: str = Column(String(16), nullable=False, default="medium")  # low|medium|high
    confidence: float = Column(Float, nullable=False, default=0.5)
    resolved: bool = Column(Boolean, nullable=False, default=False)
    resolution: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_now, server_default=func.now())

    # Relationships
    source = relationship("Source", back_populates="conflicts")

    def __repr__(self) -> str:
        return (
            f"<Conflict id={self.id!r} type={self.conflict_type!r} "
            f"severity={self.severity!r} resolved={self.resolved}>"
        )
