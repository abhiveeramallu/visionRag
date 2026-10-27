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
    modality_status: Optional[Dict[str, Any]] = None
    modalities_summary: Optional[Dict[str, Any]] = None


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
    status: Optional[str] = None
    is_genuine_conflict: Optional[bool] = None
    verification_status: Optional[str] = None
    resolution: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    query: str
    source_id: str
    conversation_id: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    conflicts: List[ConflictInfo] = Field(default_factory=list)
    confidence: float
    latency_ms: float
    retrieval_strategy_used: str
    abstained: Optional[bool] = False
    trace: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    source_id: str
    role: str
    content: str
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    strategy: Optional[str] = None
    abstained: bool = False
    latency_ms: Optional[float] = None
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    source_id: str
    title: Optional[str] = None
    messages: List[ChatMessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


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


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
