"""Domain service: turn quality value objects into a structured assessment.

``assess(...)`` is the principal entry point — it runs every signal builder
in the catalog against a ``QualityContext`` and returns a
``QualityAssessment`` whose verdict / score / reason are derived from the
signal tuple. ``evaluate(...)`` exists only as a thin back-compat wrapper
that returns the legacy ``(verdict, reason, score)`` triple consumed by the
existing ``FinancialHealthResult`` DTO (血液检查).
"""

from __future__ import annotations

from typing import Sequence

from backend.domain.quality.assessment import QualityAssessment
from backend.domain.quality.cash_flow import CashFlowQuality
from backend.domain.quality.health import FinancialHealth
from backend.domain.quality.profitability import Profitability
from backend.domain.quality.signals import (
    CORE_QUALITY_SIGNAL_BUILDERS,
    QualityContext,
    SignalBuilder,
)
from backend.domain.quality.stability import Stability
from backend.domain.verdict import Verdict

__all__ = ["QualityEvaluator"]


class QualityEvaluator:
    """Build a ``QualityAssessment`` from the four upstream quality VOs.

    A custom signal catalog can be passed for tests / experiments; defaults
    to ``CORE_QUALITY_SIGNAL_BUILDERS`` (re-exported as
    ``signals.DEFAULT_SIGNAL_BUILDERS``).
    """

    def __init__(
        self,
        signal_builders: Sequence[SignalBuilder] = CORE_QUALITY_SIGNAL_BUILDERS,
    ) -> None:
        self._builders: tuple[SignalBuilder, ...] = tuple(signal_builders)

    def assess(
        self,
        profitability: Profitability,
        cash_flow: CashFlowQuality,
        health: FinancialHealth,
        stability: Stability,
    ) -> QualityAssessment:
        ctx = QualityContext(
            profitability=profitability,
            cash_flow=cash_flow,
            stability=stability,
            health=health,
        )
        signals = tuple(builder(ctx) for builder in self._builders)
        return QualityAssessment(signals=signals)

    def evaluate(
        self,
        profitability: Profitability,
        cash_flow: CashFlowQuality,
        health: FinancialHealth,
        stability: Stability | None = None,
    ) -> tuple[Verdict, str, int]:
        """Back-compat triple. Synthesises a stability VO from the cash-flow
        VO's underlying history when callers do not yet pass one in (the
        legacy step still calls with three arguments)."""
        if stability is None:
            # The cash_flow VO already holds period-aligned series sourced
            # from the same FinancialHistory used to build profitability;
            # callers that haven't migrated yet can pass None and we fall
            # back to a stability VO with empty series. The corresponding
            # signals will mark themselves NOT_EVALUATED instead of failing.
            from backend.domain.financials.series import FinancialSeries
            stability = Stability(
                roe=FinancialSeries(),
                gross_margin=FinancialSeries(),
                net_margin=FinancialSeries(),
                annual_net_profit=FinancialSeries(),
            )
        assessment = self.assess(profitability, cash_flow, health, stability)
        return assessment.verdict, assessment.verdict_reason, assessment.score
