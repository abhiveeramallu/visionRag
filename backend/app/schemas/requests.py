from enum import Enum
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field, field_validator


class SourceType(str, Enum):
    PDF = 'pdf'
    PPT = 'ppt'
    IMAGE = 'image'
    VIDEO = 'video'
    AUDIO = 'audio'


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
    conversation_id: Optional[str] = Field(default=None, description='Optional conversation session ID')
    save_history: bool = Field(default=True, description='Whether to persist turn in conversation history')
