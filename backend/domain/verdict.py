"""Shared domain primitive: qualitative judgement label."""

from __future__ import annotations

from enum import Enum

__all__ = ["Verdict"]


class Verdict(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    NEUTRAL = "neutral"
    WARNING = "warning"
    DANGER = "danger"
