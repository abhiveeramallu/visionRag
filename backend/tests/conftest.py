"""
Pytest configuration and shared fixtures for VisionRAG-X tests.
"""
import asyncio
import pytest
from unittest.mock import MagicMock


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.llm_provider = 'openai'
    settings.openai_api_key = ''
    settings.embedding_model = 'BAAI/bge-base-en-v1.5'
    settings.embedding_device = 'cpu'
    settings.whisper_model = 'base'
    settings.whisper_device = 'cpu'
    settings.whisper_compute_type = 'int8'
    settings.ocr_language = 'en'
    settings.vision_model = ''
    settings.conflict_detection_enabled = True
    settings.conflict_severity_threshold = 0.5
    settings.retrieval_alpha = 0.6
    settings.retrieval_beta = 0.3
    settings.retrieval_gamma = 0.1
    settings.qdrant_url = 'http://localhost:6333'
    settings.qdrant_api_key = ''
    settings.qdrant_collection = 'test_collection'
    settings.upload_dir = '/tmp/visionrag_test/uploads'
    settings.frames_dir = '/tmp/visionrag_test/frames'
    settings.transcripts_dir = '/tmp/visionrag_test/transcripts'
    settings.processed_dir = '/tmp/visionrag_test/processed'
    return settings


@pytest.fixture
def sample_asr_segment():
    return {
        'text': 'The time complexity of merge sort is O(n log n)',
        'start': 10.0, 'end': 15.0,
        'timestamp_start': 10.0, 'timestamp_end': 15.0,
        'confidence': 0.92, 'modality': 'asr', 'source_id': 'test-src-1',
    }


@pytest.fixture
def sample_ocr_segment():
    return {
        'text': 'Merge Sort: O(n^2)',
        'timestamp': 12.0, 'timestamp_start': 12.0, 'timestamp_end': None,
        'page': None, 'confidence': 0.85, 'modality': 'ocr', 'source_id': 'test-src-1',
    }


@pytest.fixture
def sample_window(sample_asr_segment, sample_ocr_segment):
    return {
        'window_id': 'test-src-1_w0',
        'source_id': 'test-src-1',
        'window_start': 0.0,
        'window_end': 15.0,
        'page': None,
        'slide': None,
        'asr_segments': [sample_asr_segment],
        'ocr_segments': [sample_ocr_segment],
        'vision_segments': [],
        'formula_segments': [],
        'code_segments': [],
    }


@pytest.fixture
def sample_knowledge_units():
    return [
        {
            'id': f'unit-{i}', 'concept': f'Concept {i}',
            'content': f'Content for concept {i}. This is some educational text about topic {i}.',
            'modality': ['asr', 'ocr', 'text'][i % 3],
            'source_id': 'test-src-1',
            'timestamp_start': float(i * 15), 'timestamp_end': float((i + 1) * 15),
            'page': None, 'slide': None,
            'confidence': 0.7 + i * 0.05,
            'status': ['active', 'active', 'verified', 'disputed', 'superseded'][i % 5],
            'version': 1, 'correction_reason': None,
        }
        for i in range(5)
    ]
