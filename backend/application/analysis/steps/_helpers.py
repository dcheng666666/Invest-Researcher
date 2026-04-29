"""Shared step utilities (formatting, scoring helpers).

Kept package-private (leading underscore) so step modules can compose them
without forming an external API surface.
"""

from __future__ import annotations

from typing import Iterable

from backend.api.dto import AnnualRevenueChartPoint, PeriodMetric
from backend.domain.financials.history import FinancialHistory
from backend.domain.financials.period import ReportPeriod
from backend.domain.financials.series import FinancialSeries
from backend.domain.stocks.market_cap_history import MarketCapHistory


def to_yi(val: float) -> float:
    """Convert raw number to 亿 for display."""
    return round(val / 1e8, 2)


def series_to_period_metrics(series: FinancialSeries) -> list[PeriodMetric]:
    """Render a ``FinancialSeries`` into the API's ``PeriodMetric`` rows."""
    return [PeriodMetric(period=p.label, value=round(v, 6)) for p, v in series.pairs]


def labelled_pairs_to_period_metrics(
    pairs: Iterable[tuple[str, float]],
) -> list[PeriodMetric]:
    """Render already-labelled ``(period_label, value)`` pairs (e.g. monthly market cap)."""
    return [PeriodMetric(period=label, value=round(value, 6)) for label, value in pairs]


def yi_period_metrics(
    pairs: Iterable[tuple[ReportPeriod, float]],
) -> list[PeriodMetric]:
    """Render ``(ReportPeriod, raw_value)`` pairs scaled to 亿."""
    return [PeriodMetric(period=p.label, value=to_yi(v)) for p, v in pairs]


def ttm_chart_points(
    history: FinancialHistory, attr: str
) -> list[AnnualRevenueChartPoint]:
    """Render the TTM rolling series for ``attr`` into chart points (亿)."""
    return [
        AnnualRevenueChartPoint(period=p.label, value=round(v / 1e8, 2))
        for p, v in history.ttm_series(attr).pairs
    ]


def yi_ttm_period_metrics(history: FinancialHistory, attr: str) -> list[PeriodMetric]:
    """TTM of a yuan-denominated metric as ``PeriodMetric`` rows (亿)."""
    return [PeriodMetric(period=p.label, value=to_yi(v)) for p, v in history.ttm_series(attr).pairs]


def market_cap_history_to_yi_metrics(history: MarketCapHistory) -> list[PeriodMetric]:
    """Render a yuan-denominated ``MarketCapHistory`` as 亿-scale ``PeriodMetric`` rows."""
    return [
        PeriodMetric(period=p.period, value=to_yi(p.market_cap))
        for p in history.points
    ]


_FORMAT_GETTERS: dict[str, str] = {
    "revenue": "income_statement",
    "net_profit": "income_statement",
    "net_profit_deducted": "income_statement",
    "eps": "income_statement",
    "operating_cash_flow": "cash_flow_statement",
    "capex": "cash_flow_statement",
}


def format_history_for_prompt(history: FinancialHistory, keys: list[str]) -> str:
    """Format quarterly metrics into a readable table for an LLM prompt."""
    if not history.has_data():
        return "无数据"

    series_by_key: dict[str, FinancialSeries] = {
        key: history.series_for(key) for key in keys
    }

    lines = ["报告期 | " + " | ".join(keys)]
    lines.append("--- | " + " | ".join(["---"] * len(keys)))
    for report in history.reports:
        cells: list[str] = []
        for key in keys:
            val = next(
                (v for p, v in series_by_key[key].pairs if p == report.period),
                None,
            )
            if val is None:
                cells.append("N/A")
            elif abs(val) >= 1e8:
                cells.append(f"{val / 1e8:.2f}亿")
            elif abs(val) < 1:
                cells.append(f"{val:.2%}")
            else:
                cells.append(f"{val:.2f}")
        lines.append(f"{report.period.label} | " + " | ".join(cells))
    return "\n".join(lines)
