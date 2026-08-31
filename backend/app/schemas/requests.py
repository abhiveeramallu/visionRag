from enum import Enum
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field, field_validator


class SourceType(str, Enum):
    PDF = 'pdf'
    PPT = 'ppt'
    IMAGE = 'image'
    VIDEO = 'video'
    AUDIO = 'audio'


class SummaryType(str, Enum):
    OVERALL = 'overall'
    TOPIC = 'topic'
    TIMESTAMPED = 'timestamped'


class QuizType(str, Enum):
    MCQ = 'mcq'
    TRUE_FALSE = 'true_false'
    FILL_BLANK = 'fill_blank'
    SHORT_ANSWER = 'short_answer'


class Difficulty(str, Enum):
    EASY = 'easy'
    MEDIUM = 'medium'
    HARD = 'hard'


class NotesType(str, Enum):
    CONCISE = 'concise'
    DETAILED = 'detailed'
    REVISION = 'revision'


class YouTubeIngestRequest(BaseModel):
    url: str = Field(..., description='YouTube video URL')
    title: Optional[str] = Field(None, description='Optional custom title')

    @field_validator('url')
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not any(domain in v for domain in ['youtube.com', 'youtu.be']):
            raise ValueError('URL must be a valid YouTube URL')
        return v


class QueryRequest(BaseModel):
    source_id: str = Field(..., description='Source ID to query against')
    query: str = Field(..., min_length=1, max_length=2000, description='User question')
    top_k: int = Field(default=5, ge=1, le=20, description='Number of evidence items to retrieve')
    include_evidence: bool = Field(default=True)
    include_conflicts: bool = Field(default=True)


class SummaryRequest(BaseModel):
    source_id: str
    summary_type: SummaryType = Field(default=SummaryType.OVERALL)
    topic: Optional[str] = Field(None, description='Topic for topic-specific summary')


class QuizRequest(BaseModel):
    source_id: str
    quiz_type: QuizType = Field(default=QuizType.MCQ)
    difficulty: Difficulty = Field(default=Difficulty.MEDIUM)
    num_questions: int = Field(default=5, ge=1, le=30)
    topic: Optional[str] = None


class FlashcardRequest(BaseModel):
    source_id: str
    num_cards: int = Field(default=10, ge=1, le=50)
    topic: Optional[str] = None


class NotesRequest(BaseModel):
    source_id: str
    notes_type: NotesType = Field(default=NotesType.CONCISE)
    topic: Optional[str] = None
