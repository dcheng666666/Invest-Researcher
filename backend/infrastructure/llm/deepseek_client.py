"""DeepSeek LLM client (uses OpenAI-compatible chat-completions API)."""

from __future__ import annotations

from backend.infrastructure.llm.openai_client import OpenAILLMClient


class DeepSeekLLMClient(OpenAILLMClient):
    """Thin alias kept as its own type so we can diverge later if DeepSeek's
    API drifts from the OpenAI-compatible shape."""
