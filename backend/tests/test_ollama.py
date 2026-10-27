"""
Automated unit and integration tests for Ollama provider and citation validation.
All tests in this file use controlled test doubles / mocks to verify:
1. Configuration resolution and Ollama provider initialization.
2. Request payload formatting (model, messages, temperature, num_predict, json_mode).
3. Response content parsing from Ollama /api/chat format.
4. Error handling for unreachable service (ConnectError), missing model (404), and timeout.
5. Grounded citation validation in AnswerGenerator (valid index preservation vs hallucinated citation pruning).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.config import Settings
from app.generation.llm import LLMClient, LLMProvider, ConfigurationError
from app.generation.answer import AnswerGenerator, validate_citations


def test_ollama_provider_configuration_defaults():
    """Verify that settings default to Ollama provider with llama3.2:3b and port 11434."""
    settings = Settings()
    assert settings.llm_provider == 'ollama'
    assert settings.ollama_base_url == 'http://localhost:11434'
    assert settings.ollama_model == 'llama3.2:3b'
    assert settings.llm_timeout_seconds == 120
    assert settings.is_llm_configured() is True


@pytest.mark.asyncio
async def test_ollama_complete_request_formatting():
    """Verify that _ollama_complete formats the POST payload to /api/chat correctly."""
    settings = Settings(
        llm_provider='ollama',
        ollama_base_url='http://localhost:11434',
        ollama_model='llama3.2:3b',
        llm_timeout_seconds=60,
    )
    client = LLMClient(settings)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'model': 'llama3.2:3b',
        'message': {'role': 'assistant', 'content': 'Merge sort runs in O(n log n) [1].'},
        'done': True,
    }

    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        ans = await client.complete(
            system_prompt='You are VisionRAG-X.',
            user_prompt='What is the complexity of merge sort?',
            temperature=0.2,
            max_tokens=500,
        )

        assert 'O(n log n)' in ans
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        endpoint = call_kwargs[0][0]
        payload = call_kwargs[1]['json']

        assert endpoint == 'http://localhost:11434/api/chat'
        assert payload['model'] == 'llama3.2:3b'
        assert payload['messages'][0] == {'role': 'system', 'content': 'You are VisionRAG-X.'}
        assert payload['messages'][1] == {'role': 'user', 'content': 'What is the complexity of merge sort?'}
        assert payload['options']['temperature'] == 0.2
        assert payload['options']['num_predict'] == 500
        assert payload['stream'] is False


@pytest.mark.asyncio
async def test_ollama_complete_service_unreachable():
    """Verify that httpx.ConnectError raises a clean ConfigurationError with recovery instructions."""
    settings = Settings(llm_provider='ollama')
    client = LLMClient(settings)

    with patch('httpx.AsyncClient.post', side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(ConfigurationError) as exc_info:
            await client.complete('sys', 'user')
        assert 'not reachable' in str(exc_info.value).lower()
        assert 'ollama serve' in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_ollama_complete_model_not_found():
    """Verify that HTTP 404 from Ollama raises ConfigurationError advising 'ollama pull'."""
    settings = Settings(llm_provider='ollama', ollama_model='non-existent-model')
    client = LLMClient(settings)

    mock_res = MagicMock()
    mock_res.status_code = 404

    with patch('httpx.AsyncClient.post', return_value=mock_res):
        with pytest.raises(ConfigurationError) as exc_info:
            await client.complete('sys', 'user')
        assert 'not found' in str(exc_info.value).lower()
        assert 'ollama pull' in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_ollama_complete_timeout_handling():
    """Verify that request timeout raises TimeoutError with the configured timeout duration."""
    settings = Settings(llm_provider='ollama', llm_timeout_seconds=30)
    client = LLMClient(settings)

    with patch('httpx.AsyncClient.post', side_effect=httpx.TimeoutException("Read timeout")):
        with pytest.raises(TimeoutError) as exc_info:
            await client.complete('sys', 'user')
        assert 'timed out after 30' in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_ollama_health_check_reporting():
    """Verify health_check queries /api/tags and reports installed models and latency."""
    settings = Settings(llm_provider='ollama', ollama_model='llama3.2:3b')
    client = LLMClient(settings)

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        'models': [
            {'name': 'llama3.2:3b', 'size': 2019393189},
            {'name': 'mistral:7b', 'size': 4100000000},
        ]
    }

    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_res
        health = await client.health_check()

        assert health['available'] is True
        assert health['provider'] == 'ollama'
        assert health['model'] == 'llama3.2:3b'
        assert health['model_installed'] is True
        assert 'llama3.2:3b' in health['installed_models']
        assert health['error'] is None


def test_citation_validation_preserves_valid_and_prunes_hallucinated():
    """Verify validate_citations preserves valid evidence indices and strips hallucinated ones."""
    evidence = [
        {'id': 'ku_01', 'text': 'Merge sort has O(n log n) complexity in all cases.', 'page': 1},
        {'id': 'ku_02', 'text': 'Binary search runs in O(log n) time.', 'page': 2},
    ]

    # Model emitted valid [1], [2] as well as hallucinated [99] and [5]
    raw_answer = "Merge sort is O(n log n) [1] while binary search is O(log n) [2]. Extra hallucination [99] and [5]."

    sanitized, valid, invalid = validate_citations(raw_answer, evidence)

    assert valid == [1, 2]
    assert invalid == [99, 5]
    assert "[1]" in sanitized
    assert "[2]" in sanitized
    assert "[99]" not in sanitized
    assert "[5]" not in sanitized
    assert "Extra hallucination and." in sanitized or "Extra hallucination" in sanitized


@pytest.mark.asyncio
async def test_answer_generator_invokes_llm_and_validates_citations():
    """Verify AnswerGenerator passes evidence context to LLM and returns sanitized citations."""
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="According to [1], merge sort worst case is O(n log n) [1]. See also [88].")

    evidence = [
        {'id': 'ku_01', 'text': 'Merge sort worst-case is O(n log n).', 'confidence': 0.95, 'page': 1},
    ]
    gen = AnswerGenerator(mock_llm, None)

    res = await gen.generate(
        query="What is merge sort time complexity?",
        evidence=evidence,
        conflicts=[],
        source_title="Algorithms Course",
        abstain=False,
    )

    assert res['abstained'] is False
    assert '[1]' in res['answer']
    assert '[88]' not in res['answer']  # Hallucinated citation pruned
    assert res['valid_citation_indices'] == [1]
    assert res['invalid_citation_indices'] == [88]
    assert len(res['cited_evidence']) == 1
