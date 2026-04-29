"""Step 1: 业绩长跑 — multi-year revenue / profit growth track."""

from __future__ import annotations

from backend.application.analysis.context import AnalysisContext
from backend.application.analysis.results import GrowthTrackResult
from backend.application.analysis.steps._helpers import (
    series_to_period_metrics,
    ttm_chart_points,
    yi_period_metrics,
)
from backend.domain.verdict import Verdict


def _evaluate_verdict(
    profit_growth_values: list[float],
    rev_cagr: float | None,
    profit_cagr: float | None,
) -> tuple[Verdict, str, int]:
    if rev_cagr is None or profit_cagr is None:
        raise ValueError("Unable to evaluate verdict: missing revenue/profit CAGR.")

    n_periods = len(profit_growth_values)
    has_negative = any(g < -0.10 for g in profit_growth_values) if profit_growth_values else False
    positive_count = sum(1 for g in profit_growth_values if g > 0)
    total_periods = n_periods

    if profit_cagr >= 0.15 and not has_negative:
        return (
            Verdict.EXCELLENT,
            (
                f"扣非净利润CAGR {profit_cagr:.1%}，营收CAGR {rev_cagr:.1%}，"
                f"连续{n_periods}个报告期稳步增长，属于优质标的。"
            ),
            5,
        )
    if profit_cagr >= 0.08 and positive_count >= total_periods * 0.7:
        return (
            Verdict.GOOD,
            (
                f"扣非净利润CAGR {profit_cagr:.1%}，增长较为稳健，"
                f"过去{total_periods}个报告期中{positive_count}个保持增长。"
            ),
            4,
        )
    if has_negative and sum(1 for g in profit_growth_values if g < -0.10) >= 3:
        return (
            Verdict.WARNING,
            "利润波动剧烈，多次出现10%以上跌幅，呈现周期股特征，不适用传统价值投资的长期持有逻辑。",
            2,
        )
    if rev_cagr >= 0.08 and (profit_cagr is None or profit_cagr < 0.03):
        return (
            Verdict.DANGER,
            (
                f"营收CAGR {rev_cagr:.1%}保持增长，但利润CAGR仅{profit_cagr:.1%}，"
                f"典型的增收不增利，说明竞争加剧或成本失控。"
            ),
            1,
        )
    return (
        Verdict.NEUTRAL,
        f"扣非净利润CAGR {profit_cagr:.1%}，营收CAGR {rev_cagr:.1%}，表现平平。",
        3,
    )


def analyze(ctx: AnalysisContext) -> GrowthTrackResult:
    financial = ctx.financials
    revenue = financial.income_series("revenue")
    profit = financial.income_series("net_profit_deducted")
    rev_growth = financial.metric_series("revenue_growth")
    profit_growth = financial.metric_series("profit_growth")

    rev_cagr = revenue.annual_only().cagr()
    profit_cagr = profit.annual_only().cagr()
    verdict, verdict_reason, score = _evaluate_verdict(
        profit_growth.values, rev_cagr, profit_cagr
    )

    return GrowthTrackResult(
        single_quarter_revenue=yi_period_metrics(
            financial.single_quarter_series("revenue").pairs
        ),
        single_quarter_profit=yi_period_metrics(
            financial.single_quarter_series("net_profit_deducted").pairs
        ),
        revenue_cagr=round(rev_cagr, 4) if rev_cagr is not None else None,
        profit_cagr=round(profit_cagr, 4) if profit_cagr is not None else None,
        revenue_growth_rates=series_to_period_metrics(rev_growth),
        profit_growth_rates=series_to_period_metrics(profit_growth),
        ttm_revenue_chart=ttm_chart_points(financial, "revenue"),
        ttm_profit_chart=ttm_chart_points(financial, "net_profit_deducted"),
        verdict=verdict,
        verdict_reason=verdict_reason,
        score=score,
    )
