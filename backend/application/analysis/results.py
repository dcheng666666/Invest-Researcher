"""Per-step result Pydantic models consumed by the streaming analysis API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from backend.api.dto import AnnualRevenueChartPoint, PeriodMetric
from backend.domain.verdict import Verdict


class PayoutRatioBarPoint(BaseModel):
    """One fiscal-year bar: payout ratio and number of cash dividend events."""

    period: str
    value: float
    distribution_count: int


class GrowthTrackResult(BaseModel):
    """业绩长跑 — multi-year revenue / profit growth track."""

    single_quarter_revenue: list[PeriodMetric] = []
    single_quarter_profit: list[PeriodMetric] = []
    revenue_cagr: float | None = None
    profit_cagr: float | None = None
    revenue_growth_rates: list[PeriodMetric] = []
    profit_growth_rates: list[PeriodMetric] = []
    ttm_revenue_chart: list[AnnualRevenueChartPoint] = []
    ttm_profit_chart: list[AnnualRevenueChartPoint] = []
    verdict: Verdict = Verdict.NEUTRAL
    verdict_reason: str = ""
    score: int = 3


class QualityHeatTile(BaseModel):
    """One cell in the blood-check quality heatmap (maps ``QualitySignal``)."""

    name: str
    label: str
    status: Literal["pass", "warn", "fail", "n/a"]
    detail: str


class IndustryBenchmarkRef(BaseModel):
    """Industry median snapshot for chart reference lines (display-only)."""

    industry_key: str
    as_of: str
    roe_median: float | None = None
    roa_median: float | None = None
    gross_margin_median: float | None = None
    debt_ratio_median: float | None = None


class FinancialHealthResult(BaseModel):
    """血液检查 — financial-health signals (ROE / ROA / FCF / receivables / debt)."""

    roe: list[PeriodMetric] = []
    roa: list[PeriodMetric] = []
    free_cash_flow: list[PeriodMetric] = []
    free_cash_flow_ttm: list[PeriodMetric] = []
    receivable_ratio: list[PeriodMetric] = []
    inventory_ratio: list[PeriodMetric] = []
    debt_ratio: list[PeriodMetric] = []
    avg_roe: float | None = None
    fcf_positive_years: int = 0
    quality_heatmap: list[QualityHeatTile] = []
    industry_benchmark: IndustryBenchmarkRef | None = None
    verdict: Verdict = Verdict.NEUTRAL
    verdict_reason: str = ""
    score: int = 3


class PayoutResult(BaseModel):
    """厚道程度 — shareholder returns (payout ratio + dividend yield)."""

    payout_ratios: list[PayoutRatioBarPoint] = []
    avg_payout_ratio: float | None = None
    latest_dividend_yield: float | None = None
    verdict: Verdict = Verdict.NEUTRAL
    verdict_reason: str = ""
    score: int = 3


class MoatResult(BaseModel):
    """生意逻辑 — business moat (display-only, not counted in overall score)."""

    gross_margins: list[PeriodMetric] = []
    net_margins: list[PeriodMetric] = []
    rd_expense_ratios: list[PeriodMetric] = []
    selling_expense_ratios: list[PeriodMetric] = []
    gross_margin_trend: str = ""
    llm_analysis: str = ""
    verdict: Verdict = Verdict.NEUTRAL
    verdict_reason: str = ""
    score: int = 3


class ValuationResult(BaseModel):
    """估值称重 — PE history, percentile, PEG, market cap reasonability."""

    pe_history: list[PeriodMetric] = []
    pb_history: list[PeriodMetric] = []
    current_pe: float | None = None
    current_pb: float | None = None
    pe_percentile: float | None = None
    pb_percentile: float | None = None
    pe_mean: float | None = None
    pe_std_dev: float | None = None
    pe_low: float | None = None
    pe_high: float | None = None
    peg: float | None = None
    #: Implied spot if TTM PE sat at historical mean minus one std-dev; None when
    #: band is unavailable, target PE is not positive, inputs are missing, or
    #: current PE is already at or below that level.
    price_at_pe_minus_one_sigma: float | None = None
    #: Implied spot if TTM PE sat at historical mean (upper end of the PE band
    #: mapped price range paired with ``price_at_pe_minus_one_sigma``).
    price_at_pe_mean: float | None = None
    # Display-only series for the market-cap-vs-业绩 reasonability chart;
    # used by the frontend to visualise whether market cap tracks earnings.
    ttm_revenue_chart: list[AnnualRevenueChartPoint] = []
    ttm_profit_chart: list[AnnualRevenueChartPoint] = []
    market_cap_monthly: list[PeriodMetric] = []
    verdict: Verdict = Verdict.NEUTRAL
    verdict_reason: str = ""
    score: int = 3
