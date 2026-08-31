"""
VisionRAG-X Configuration.
All settings loaded from environment variables via .env file.
No hard-coded secrets.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    # === LLM ===
    llm_provider: str = Field(default='openai', description='LLM provider: openai | gemini | local')
    openai_api_key: str = Field(default='', description='OpenAI API key')
    openai_base_url: str = Field(default='https://api.openai.com/v1')
    openai_model: str = Field(default='gpt-4o')
    gemini_api_key: str = Field(default='', description='Google Gemini API key')
    gemini_model: str = Field(default='gemini-1.5-pro')
    local_llm_base_url: str = Field(default='http://localhost:11434/v1')
    local_llm_model: str = Field(default='llama3.1:8b')

    # === Embedding ===
    embedding_model: str = Field(default='BAAI/bge-base-en-v1.5')
    embedding_device: str = Field(default='cpu')

    # === Qdrant ===
    qdrant_url: str = Field(default='http://localhost:6333')
    qdrant_api_key: str = Field(default='')
    qdrant_collection: str = Field(default='visionrag_x')

    # === PostgreSQL ===
    postgres_url: str = Field(default='postgresql+asyncpg://visionrag:visionrag@localhost:5432/visionrag_x')
    postgres_sync_url: str = Field(default='postgresql://visionrag:visionrag@localhost:5432/visionrag_x')

    # === Storage ===
    upload_dir: str = Field(default='./data/uploads')
    frames_dir: str = Field(default='./data/frames')
    transcripts_dir: str = Field(default='./data/transcripts')
    processed_dir: str = Field(default='./data/processed')

    # === Processing ===
    frame_interval: float = Field(default=2.0, description='Seconds between frame samples')
    whisper_model: str = Field(default='base', description='tiny|base|small|medium|large-v2')
    whisper_device: str = Field(default='cpu', description='cpu|cuda')
    whisper_compute_type: str = Field(default='int8', description='int8|float16|float32')
    ocr_language: str = Field(default='en')
    vision_model: str = Field(default='', description='Leave empty to disable vision descriptions')

    # === Retrieval ===
    retrieval_alpha: float = Field(default=0.6, description='Semantic weight')
    retrieval_beta: float = Field(default=0.3, description='Lexical weight')
    retrieval_gamma: float = Field(default=0.1, description='Knowledge confidence weight')

    # === Conflict Detection ===
    conflict_detection_enabled: bool = Field(default=True)
    conflict_severity_threshold: float = Field(default=0.5)

    # === App ===
    app_host: str = Field(default='0.0.0.0')
    app_port: int = Field(default=8000)
    debug: bool = Field(default=False)
    cors_origins: str = Field(default='http://localhost:3000,http://localhost:5173')
    secret_key: str = Field(default='change-this-to-a-random-secret-key')

    def get_cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(',')]

    def is_llm_configured(self) -> bool:
        if self.llm_provider == 'openai':
            return bool(self.openai_api_key and self.openai_api_key != 'your-openai-api-key-here')
        elif self.llm_provider == 'gemini':
            return bool(self.gemini_api_key and self.gemini_api_key != 'your-gemini-api-key-here')
        elif self.llm_provider == 'local':
            return bool(self.local_llm_base_url)
        return False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
