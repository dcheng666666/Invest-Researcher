"""Application orchestration: build context once, then run each registered step."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.application.analysis.context import AnalysisContext
from backend.application.analysis.score_aggregator import overall_score
from backend.application.analysis.step_registry import STEP_CONFIGS, STEP_TITLES
from backend.repositories import (
    dividend_repository,
    financial_repository,
    security_repository,
    symbol_repository,
)

logger = logging.getLogger(__name__)


def build_context(code: str) -> AnalysisContext | None:
    financials = financial_repository.get_financial_history(code)
    security = security_repository.load_security_with_history(code)
    dividends = dividend_repository.get_history(code)

    return AnalysisContext(
        code=code,
        security=security,
        financials=financials,
        dividends=dividends,
        as_of=datetime.utcnow(),
    )


def run_steps(
    ctx: AnalysisContext,
) -> tuple[dict[int, dict[str, Any]], dict[int, str], list[int]]:
    """Run every registered step against the context.

    Returns ``(results, errors, scores)`` where ``results`` is keyed by step
    number with the ``model_dump`` of the corresponding pydantic result.
    """
    results: dict[int, dict[str, Any]] = {}
    errors: dict[int, str] = {}
    scores: list[int] = []
    for cfg in STEP_CONFIGS:
        try:
            model = cfg.analyzer(ctx)
            dumped = model.model_dump()
            results[cfg.number] = dumped
            scores.append(int(dumped.get("score", 3)))
        except Exception as e:
            logger.exception("Analysis step %d failed for %s", cfg.number, ctx.code)
            errors[cfg.number] = str(e)
            scores.append(0)
    return results, errors, scores


def stock_display_name(code: str) -> str:
    return symbol_repository.display_name(code)


__all__ = [
    "STEP_CONFIGS",
    "STEP_TITLES",
    "build_context",
    "run_steps",
    "stock_display_name",
    "overall_score",
]
