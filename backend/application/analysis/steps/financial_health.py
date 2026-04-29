"""Step 2: 血液检查 — orchestrate quality domain into the FinancialHealthResult DTO."""

from __future__ import annotations

from backend.application.analysis.context import AnalysisContext
from backend.application.analysis.results import (
    FinancialHealthResult,
    IndustryBenchmarkRef,
    QualityHeatTile,
)
from backend.repositories import industry_benchmark_repository
from backend.application.analysis.steps._helpers import (
    series_to_period_metrics,
    yi_period_metrics,
    yi_ttm_period_metrics,
)
from backend.domain.quality.cash_flow import CashFlowQuality
from backend.domain.quality.evaluator import QualityEvaluator
from backend.domain.quality.health import FinancialHealth
from backend.domain.quality.profitability import Profitability
from backend.domain.quality.stability import Stability


def analyze(ctx: AnalysisContext) -> FinancialHealthResult:
    history = ctx.financials
    profitability = Profitability.from_history(history)
    cash_flow = CashFlowQuality.from_history(history)
    health = FinancialHealth.from_history(history)
    stability = Stability.from_history(history)

    assessment = QualityEvaluator().assess(
        profitability, cash_flow, health, stability
    )
    verdict = assessment.verdict
    verdict_reason = assessment.verdict_reason
    score = assessment.score

    roe = profitability.roe
    roa = profitability.roa
    avg_roe = roe.average(annual_only=True)

    quality_heatmap = [
        QualityHeatTile(
            name=s.name,
            label=s.label,
            status=s.status.value,
            detail=s.detail,
        )
        for s in assessment.signals
    ]

    industry_benchmark: IndustryBenchmarkRef | None = None
    ind = ctx.industry
    if ind:
        bench = industry_benchmark_repository.get_by_industry_key(ind)
        if bench is not None:
            industry_benchmark = IndustryBenchmarkRef(
                industry_key=bench.industry_key,
                as_of=bench.as_of,
                roe_median=bench.roe_median,
                roa_median=bench.roa_median,
                gross_margin_median=bench.gross_margin_median,
                debt_ratio_median=bench.debt_ratio_median,
            )

    return FinancialHealthResult(
        roe=series_to_period_metrics(roe.quarterly),
        roa=series_to_period_metrics(roa.quarterly),
        free_cash_flow=yi_period_metrics(cash_flow.free_cash_flow.pairs),
        free_cash_flow_ttm=yi_ttm_period_metrics(history, "free_cash_flow"),
        receivable_ratio=series_to_period_metrics(health.receivable_turnover_days),
        inventory_ratio=series_to_period_metrics(health.inventory_turnover_days),
        debt_ratio=series_to_period_metrics(health.debt_ratio),
        avg_roe=round(avg_roe, 4) if avg_roe is not None else None,
        fcf_positive_years=cash_flow.positive_periods,
        quality_heatmap=quality_heatmap,
        industry_benchmark=industry_benchmark,
        verdict=verdict,
        verdict_reason=verdict_reason,
        score=score,
    )
