"""LLM prompt templates loaded from sibling ``.txt`` resources."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Read ``<name>.txt`` from this package, cached for the process lifetime."""
    path = _PROMPT_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()
