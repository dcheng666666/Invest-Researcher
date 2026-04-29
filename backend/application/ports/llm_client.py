"""Application-layer port for any LLM-style completion provider."""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Anything that takes a system + user prompt and returns text."""

    def complete(self, system_prompt: str, user_prompt: str) -> str: ...
