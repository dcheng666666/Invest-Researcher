"""OpenAI-compatible LLM client (also handles DeepSeek with custom base_url)."""

from __future__ import annotations

import logging

from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAILLMClient:
    """Implements ``application.ports.llm_client.LLMClient`` Protocol."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int = 2000,
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI LLM call failed: %s", e)
            return f"LLM分析暂时不可用: {e}"
