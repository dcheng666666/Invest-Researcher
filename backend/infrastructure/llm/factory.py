"""Pick a concrete ``LLMClient`` implementation based on app settings."""

from __future__ import annotations

from backend.config import settings
from backend.infrastructure.llm.anthropic_client import AnthropicLLMClient
from backend.infrastructure.llm.deepseek_client import DeepSeekLLMClient
from backend.infrastructure.llm.openai_client import OpenAILLMClient


def build_llm_client():
    """Return an object satisfying the ``LLMClient`` Protocol from settings."""
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicLLMClient(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
    if provider == "deepseek":
        return DeepSeekLLMClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
    return OpenAILLMClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
    )
