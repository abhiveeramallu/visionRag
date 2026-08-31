from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


class ComponentStatus(BaseModel):
    available: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    details: Optional[str] = None


class HealthResponse(BaseModel):
    status: str  # 'healthy' | 'degraded' | 'unhealthy'
    version: str
    components: Dict[str, ComponentStatus]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SourceResponse(BaseModel):
    id: str
    title: str
    source_type: str
    status: str
    url: Optional[str] = None
    file_path: Optional[str] = None
    duration: Optional[float] = None
    num_pages: Optional[int] = None
    channel: Optional[str] = None
    upload_date: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class JobStatusResponse(BaseModel):
    job_id: str
    source_id: str
    status: JobStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    current_step: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EvidenceItem(BaseModel):
    text: str
    source_id: str
    modality: str  # asr, ocr, vision, formula, code
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    page: Optional[int] = None
    slide: Optional[int] = None
    confidence: float
    knowledge_unit_id: Optional[str] = None
    version: Optional[int] = None
    status: Optional[str] = None  # active, superseded, disputed, verified


class ConflictInfo(BaseModel):
    conflict_id: str
    conflict_type: str
    sources: List[str]  # modalities involved
    claims: List[str]
    timestamp: Optional[float] = None
    page: Optional[int] = None
    severity: str  # low, medium, high
    confidence: float


class QueryResponse(BaseModel):
    answer: str
    query: str
    source_id: str
    evidence: List[EvidenceItem] = Field(default_factory=list)
    conflicts: List[ConflictInfo] = Field(default_factory=list)
    confidence: float
    latency_ms: float
    retrieval_strategy_used: str


class SummarySection(BaseModel):
    title: str
    content: str
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    page: Optional[int] = None


class SummaryResponse(BaseModel):
    source_id: str
    summary_type: str
    content: str
    sections: List[SummarySection] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class QuizQuestion(BaseModel):
    question_id: str
    question: str
    question_type: str
    options: Optional[List[str]] = None  # for MCQ
    answer: str
    explanation: str
    difficulty: str
    source_evidence: Optional[EvidenceItem] = None


class QuizResponse(BaseModel):
    source_id: str
    questions: List[QuizQuestion]
    topic: Optional[str] = None
    difficulty: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class FlashcardItem(BaseModel):
    card_id: str
    front: str  # question
    back: str   # answer
    concept: str
    source_evidence: Optional[EvidenceItem] = None
    confidence: float = 0.5


class FlashcardResponse(BaseModel):
    source_id: str
    cards: List[FlashcardItem]
    topic: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeUnitResponse(BaseModel):
    id: str
    concept: str
    content: str
    modality: str
    source_id: str
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    page: Optional[int] = None
    slide: Optional[int] = None
    confidence: float
    status: str
    version: int
    correction_reason: Optional[str] = None
    evidence_count: int = 0
    conflict_count: int = 0


class NotesSection(BaseModel):
    title: str
    content: str
    page: Optional[int] = None


class NotesResponse(BaseModel):
    source_id: str
    notes_type: str
    content: str
    sections: List[NotesSection] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
