"""
LLM abstraction for VisionRAG-X.

Supports OpenAI-compatible, Google Gemini, and local Llama-compatible endpoints.
Never hard-codes API keys — all config comes from environment variables.
"""
import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OPENAI = 'openai'
    GEMINI = 'gemini'
    LOCAL = 'local'


class ConfigurationError(Exception):
    """Raised when the LLM is not properly configured."""
    pass


class LLMClient:
    """
    Multi-provider LLM client.

    Provider is selected by the LLM_PROVIDER environment variable.
    Supported values: 'openai', 'gemini', 'local'.

    For 'local': uses the OpenAI-compatible API (works with Ollama, vLLM, LM Studio).
    For 'openai': uses the official OpenAI Python SDK.
    For 'gemini': uses the google-generativeai SDK.
    """

    def __init__(self, settings: Any):
        self.settings = settings

    # ------------------------------------------------------------------
    # Provider check
    # ------------------------------------------------------------------

    def _assert_openai_configured(self) -> None:
        key = getattr(self.settings, 'openai_api_key', '')
        if not key or key in ('', 'your-openai-api-key-here'):
            raise ConfigurationError(
                'OpenAI API key not set. '
                'Set OPENAI_API_KEY in your .env file to use the OpenAI provider.'
            )

    def _assert_gemini_configured(self) -> None:
        key = getattr(self.settings, 'gemini_api_key', '')
        if not key or key in ('', 'your-gemini-api-key-here'):
            raise ConfigurationError(
                'Gemini API key not set. '
                'Set GEMINI_API_KEY in your .env file to use the Gemini provider.'
            )

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    async def _openai_complete(
        self,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self._assert_openai_configured()
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ConfigurationError('openai package not installed. Run: pip install openai')

        client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )
        response = await client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ''

    async def _gemini_complete(
        self,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self._assert_gemini_configured()
        try:
            import google.generativeai as genai
        except ImportError:
            raise ConfigurationError(
                'google-generativeai package not installed. '
                'Run: pip install google-generativeai'
            )

        genai.configure(api_key=self.settings.gemini_api_key)
        model = genai.GenerativeModel(
            model_name=self.settings.gemini_model,
            system_instruction=system,
        )
        response = await model.generate_content_async(
            user,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text or ''

    async def _local_complete(
        self,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """OpenAI-compatible local API (Ollama, vLLM, LM Studio)."""
        base_url = getattr(self.settings, 'local_llm_base_url', 'http://localhost:11434/v1')
        model = getattr(self.settings, 'local_llm_model', 'llama3.1:8b')
        if not base_url:
            raise ConfigurationError(
                'LOCAL_LLM_BASE_URL not set. '
                'Set it to your Ollama/vLLM/LM Studio endpoint (e.g. http://localhost:11434/v1).'
            )
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ConfigurationError('openai package not installed. Run: pip install openai')

        client = AsyncOpenAI(api_key='not-needed', base_url=base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ''

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """
        Generate a completion from the configured LLM provider.

        Raises ConfigurationError if the provider is not properly set up.
        Never silently returns dummy text — callers receive a clear error.
        """
        provider = getattr(self.settings, 'llm_provider', 'openai').lower()
        logger.debug('LLM completion: provider=%s model_tokens=%d', provider, max_tokens)

        if provider == LLMProvider.OPENAI:
            return await self._openai_complete(system_prompt, user_prompt, temperature, max_tokens)
        elif provider == LLMProvider.GEMINI:
            return await self._gemini_complete(system_prompt, user_prompt, temperature, max_tokens)
        elif provider == LLMProvider.LOCAL:
            return await self._local_complete(system_prompt, user_prompt, temperature, max_tokens)
        else:
            raise ConfigurationError(
                f'Unknown LLM_PROVIDER: "{provider}". '
                'Valid values: openai | gemini | local'
            )

    async def health_check(self) -> dict:
        """
        Test LLM connectivity with a minimal prompt.

        Returns a dict suitable for inclusion in the /api/health response.
        """
        import time
        provider = getattr(self.settings, 'llm_provider', 'openai')
        model_names = {
            'openai': getattr(self.settings, 'openai_model', 'gpt-4o'),
            'gemini': getattr(self.settings, 'gemini_model', 'gemini-1.5-pro'),
            'local': getattr(self.settings, 'local_llm_model', 'unknown'),
        }
        try:
            t0 = time.perf_counter()
            await self.complete('You are a test assistant.', 'Reply with: OK', max_tokens=5)
            latency_ms = (time.perf_counter() - t0) * 1000
            return {
                'available': True,
                'provider': provider,
                'model': model_names.get(provider, 'unknown'),
                'latency_ms': round(latency_ms, 1),
                'error': None,
            }
        except ConfigurationError as e:
            return {'available': False, 'provider': provider, 'model': None, 'error': str(e)}
        except Exception as e:
            return {'available': False, 'provider': provider, 'model': None, 'error': f'LLM error: {e}'}
