"""Anthropic Claude LLM client."""

from __future__ import annotations

import logging

from anthropic import Anthropic

logger = logging.getLogger(__name__)


class AnthropicLLMClient:
    """Implements ``application.ports.llm_client.LLMClient`` Protocol."""

    def __init__(self, api_key: str, model: str, max_tokens: int = 2000) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return resp.content[0].text
        except Exception as e:
            logger.error("Anthropic LLM call failed: %s", e)
            return f"LLM分析暂时不可用: {e}"
