"""Step 5: 估值称重 — orchestrate valuation domain into the ValuationResult DTO."""

from __future__ import annotations

from backend.application.analysis.context import AnalysisContext
from backend.application.analysis.results import ValuationResult
from backend.application.analysis.steps._helpers import (
    labelled_pairs_to_period_metrics,
    market_cap_history_to_yi_metrics,
    ttm_chart_points,
)
from backend.domain.dividends.aggregation import aggregate_history
from backend.domain.dividends.amounts import DividendYield
from backend.domain.dividends.history import DividendHistory
from backend.domain.financials.history import FinancialHistory
from backend.domain.quality.profitability import ReturnOnEquity
from backend.domain.valuation.band import HistoricalBand
from backend.domain.valuation.evaluator import ValuationEvaluator
from backend.domain.valuation.history import (
    ValuationHistory,
    ttm_profit_timeline_from_history,
)
from backend.domain.valuation.multiples import PEGRatio
from backend.domain.valuation.snapshot import ValuationSnapshot


def analyze(ctx: AnalysisContext) -> ValuationResult:
    history = ctx.financials

    roe = ReturnOnEquity.from_history(history)
    dividend_yield = _latest_dividend_yield(ctx.dividends, ctx.snapshot.current_price)
    snapshot = ValuationSnapshot.from_inputs(
        ctx.snapshot, history, roe, dividend_yield=dividend_yield
    )

    market_cap_history = ctx.security.market_cap_history
    valuation_history = ValuationHistory.from_inputs(
        market_cap_history.as_pairs(),
        ttm_profit_timeline_from_history(history),
    )

    if valuation_history.is_empty():
        raise ValueError(
            "Unable to build valuation history: missing aligned monthly market cap and TTM profit data."
        )

    band = valuation_history.band()
    percentile = valuation_history.percentile_of(snapshot.pe_value)

    avg_growth = _recent_avg_profit_growth(history)
    peg = PEGRatio.from_pe(snapshot.pe_ratio, avg_growth)

    assessment = ValuationEvaluator().evaluate(snapshot, valuation_history, peg=peg)

    price_at_pe_minus_one_sigma = compute_price_at_pe_minus_one_sigma(snapshot, band)

    return ValuationResult(
        pe_history=labelled_pairs_to_period_metrics(valuation_history.metric_pairs()),
        pb_history=[],
        current_pe=round(snapshot.pe_value, 2) if snapshot.pe_value else None,
        current_pb=round(snapshot.pb_value, 2) if snapshot.pb_value else None,
        pe_percentile=(
            round(percentile.value, 4) if percentile is not None else None
        ),
        pb_percentile=None,
        pe_mean=band.mean if band is not None else None,
        pe_std_dev=band.std_dev if band is not None else None,
        pe_low=band.low if band is not None else None,
        pe_high=band.high if band is not None else None,
        peg=round(peg.value, 2) if peg is not None else None,
        price_at_pe_minus_one_sigma=(
            round(price_at_pe_minus_one_sigma, 2)
            if price_at_pe_minus_one_sigma is not None
            else None
        ),
        ttm_revenue_chart=ttm_chart_points(history, "revenue"),
        ttm_profit_chart=ttm_chart_points(history, "net_profit_deducted"),
        market_cap_monthly=market_cap_history_to_yi_metrics(market_cap_history),
        verdict=assessment.verdict,
        verdict_reason=assessment.reason,
        score=assessment.score,
    )


def compute_price_at_pe_minus_one_sigma(
    snapshot: ValuationSnapshot, band: HistoricalBand | None
) -> float | None:
    """Spot price if TTM PE were at historical mean minus one std-dev.

    Uses ``PE_target = mean - std`` from the same sample as ``ValuationHistory``;
    scales spot by ``PE_target / PE_current`` with unchanged TTM earnings and share
    count. Returns ``None`` when the band is missing, ``std_dev`` is non-positive,
    ``PE_target`` is not positive, spot inputs are invalid, or current PE is already
    at or below ``PE_target`` (no separate upside reference).
    """
    if band is None or band.std_dev <= 0:
        return None
    target_pe = band.mean - band.std_dev
    if target_pe <= 0:
        return None
    current_pe = snapshot.pe_value
    price = snapshot.price
    if current_pe is None or current_pe <= 0 or price is None or price <= 0:
        return None
    if current_pe <= target_pe:
        return None
    return price * (target_pe / current_pe)


def _recent_avg_profit_growth(history: FinancialHistory) -> float | None:
    """Latest 3 annual profit-growth readings, averaged for PEG composition."""
    annual_profit_growth = history.metric_series("profit_growth").annual_only()
    if not annual_profit_growth:
        return None
    recent = annual_profit_growth.latest_n(3).values
    if not recent:
        return None
    return sum(recent) / len(recent)


def _latest_dividend_yield(
    dividends: DividendHistory, current_price: float | None
) -> float | None:
    """Latest fiscal-year DPS divided by current price, as a decimal yield."""
    if current_price is None or current_price <= 0 or dividends.is_empty:
        return None
    dividend_record = aggregate_history(dividends)
    if dividend_record.is_empty:
        return None
    latest_dps = dividend_record.annual_dps[-1][1]
    dy = DividendYield.of(latest_dps, current_price)
    return dy.value if dy is not None else None
