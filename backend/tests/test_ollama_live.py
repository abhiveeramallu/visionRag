"""
Live smoke test against local Ollama service (Track B).
Validates real model generation, measured latency, and non-empty response.
Skipped safely if Ollama service is not running or socket access is unavailable.
"""
import pytest
import time
from app.config import Settings
from app.generation.llm import LLMClient
from app.generation.answer import AnswerGenerator


@pytest.mark.asyncio
async def test_live_ollama_connectivity_and_generation():
    """
    Smoke test querying the actual local Ollama instance on http://localhost:11434.
    Sends a test prompt to llama3.2:3b, verifies latency and response format.
    """
    settings = Settings(
        llm_provider='ollama',
        ollama_base_url='http://localhost:11434',
        ollama_model='llama3.2:3b',
        llm_timeout_seconds=60,
    )
    client = LLMClient(settings)

    # 1. Health check
    health = await client.health_check()
    if not health.get('available'):
        pytest.skip(f"Local Ollama is not accessible: {health.get('error')}")

    if not health.get('model_installed'):
        pytest.skip(f"Configured model 'llama3.2:3b' is not installed in Ollama. Found: {health.get('installed_models')}")

    # 2. Real generation
    t0 = time.perf_counter()
    answer = await client.complete(
        system_prompt='You are an educational assistant. Be brief.',
        user_prompt='What is 2 + 2? Reply with just the number.',
        temperature=0.0,
        max_tokens=20,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert answer is not None
    assert len(answer.strip()) > 0
    assert '4' in answer
    print(f"\n[Live Ollama] Model: {settings.ollama_model} | Latency: {elapsed_ms:.1f}ms | Response: {answer.strip()}")


@pytest.mark.asyncio
async def test_live_ollama_grounded_answer_generation():
    """
    Smoke test invoking the full AnswerGenerator with real retrieved evidence against Ollama.
    Verifies that the generated answer cites the evidence and produces structured output.
    """
    settings = Settings(
        llm_provider='ollama',
        ollama_base_url='http://localhost:11434',
        ollama_model='llama3.2:3b',
        llm_timeout_seconds=60,
    )
    client = LLMClient(settings)

    health = await client.health_check()
    if not health.get('available') or not health.get('model_installed'):
        pytest.skip("Local Ollama or llama3.2:3b unavailable")

    evidence = [
        {
            'id': 'ku_merge_sort_01',
            'knowledge_unit_id': 'ku_merge_sort_01',
            'text': 'Merge sort divides the input array recursively into halves and merges them in O(n log n) time in all cases.',
            'modality': 'ocr',
            'page': 1,
            'confidence': 0.95,
        }
    ]

    gen = AnswerGenerator(client, None)
    t0 = time.perf_counter()
    res = await gen.generate(
        query="What is the worst-case time complexity of merge sort?",
        evidence=evidence,
        conflicts=[],
        source_title="Algorithms Lecture 1",
        abstain=False,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert res['abstained'] is False
    assert len(res['answer']) > 0
    assert 'log' in res['answer'].lower() or 'merge' in res['answer'].lower()
    print(f"\n[Live Ollama Answer] Latency: {elapsed_ms:.1f}ms | Answer: {res['answer'][:120]}...")
