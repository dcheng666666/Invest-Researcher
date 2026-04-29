"""Registry of analysis steps wired into the public 5-step framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from backend.application.analysis.context import AnalysisContext
from backend.application.analysis.steps import (
    financial_health,
    growth_track,
    moat,
    payout,
    valuation,
)


StepAnalyzer = Callable[[AnalysisContext], BaseModel]


@dataclass(frozen=True)
class StepConfig:
    number: int
    title: str
    analyzer: StepAnalyzer
    # Steps with ``scoring=False`` still run and stream their result to the
    # frontend (so users can read the verdict / charts), but are excluded
    # from the overall_score average.
    scoring: bool = True


STEP_CONFIGS: tuple[StepConfig, ...] = (
    StepConfig(1, "业绩长跑", growth_track.analyze),
    StepConfig(2, "血液检查", financial_health.analyze),
    StepConfig(3, "厚道程度", payout.analyze),
    StepConfig(4, "生意逻辑", moat.analyze, scoring=False),
    StepConfig(5, "估值称重", valuation.analyze),
)

STEP_TITLES: dict[int, str] = {cfg.number: cfg.title for cfg in STEP_CONFIGS}
