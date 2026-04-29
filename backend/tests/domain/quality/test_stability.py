"""Tests for ``backend.domain.quality.stability.Stability``."""

from __future__ import annotations

import statistics
from datetime import date

import pytest

from backend.domain.financials.accounting import (
    AccountingContext,
    PeriodPresentation,
    ReportingStandard,
)
from backend.domain.financials.history import FinancialHistory
from backend.domain.financials.metrics import FinancialMetrics
from backend.domain.financials.period import ReportPeriod
from backend.domain.financials.report import FinancialReport
from backend.domain.financials.statements import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
)
from backend.domain.quality.stability import Stability
from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol


_SYMBOL = Symbol(code="00700", market=Market.HK)
# DISCRETE so single-quarter series and ttm_series behave deterministically
# from raw per-period values.
_HK_ACCOUNTING = AccountingContext(
    currency="HKD",
    standard=ReportingStandard.IFRS,
    period_presentation=PeriodPresentation.DISCRETE,
)


def _period(year: int, quarter: int) -> ReportPeriod:
    month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    month, day = month_day[quarter]
    return ReportPeriod.quarterly(year, quarter, date(year, month, day))


def _report(
    year: int,
    quarter: int,
    *,
    roe: float | None = None,
    gross_margin: float | None = None,
    net_margin: float | None = None,
    net_profit: float | None = None,
) -> FinancialReport:
    return FinancialReport(
        security_id=_SYMBOL,
        period=_period(year, quarter),
        accounting=_HK_ACCOUNTING,
        income_statement=IncomeStatement(net_profit=net_profit),
        balance_sheet=BalanceSheet(),
        cash_flow_statement=CashFlowStatement(),
        metrics=FinancialMetrics(
            roe=roe, gross_margin=gross_margin, net_margin=net_margin
        ),
    )


def _build_full_year_history(
    annual_samples: list[tuple[int, float, float, float, float]],
) -> FinancialHistory:
    """Build an HK-style history with one full year (4 quarters) per sample.

    Each annual tuple is ``(year, roe, gross_margin, net_margin, full_year_np)``
    — the ratios are propagated to all 4 quarters (HK reports them per
    quarter), and net profit is split equally so the TTM at Q4 sums to the
    full-year value.
    """
    reports: list[FinancialReport] = []
    for year, roe, gm, nm, fy_np in annual_samples:
        per_quarter_np = fy_np / 4.0
        for q in range(1, 5):
            reports.append(
                _report(
                    year,
                    q,
                    roe=roe,
                    gross_margin=gm,
                    net_margin=nm,
                    net_profit=per_quarter_np,
                )
            )
    return FinancialHistory.of(_SYMBOL, reports)


def test_roe_stddev_uses_annual_only_view() -> None:
    history = _build_full_year_history(
        [
            (2020, 0.10, 0.30, 0.10, 100.0),
            (2021, 0.12, 0.30, 0.10, 110.0),
            (2022, 0.18, 0.30, 0.10, 120.0),
            (2023, 0.16, 0.30, 0.10, 130.0),
            (2024, 0.14, 0.30, 0.10, 140.0),
        ]
    )
    stab = Stability.from_history(history)

    expected = statistics.stdev([0.10, 0.12, 0.18, 0.16, 0.14])
    assert stab.roe_stddev() == pytest.approx(expected)


def test_margin_stddev_picks_up_dispersion() -> None:
    history = _build_full_year_history(
        [
            (2020, 0.20, 0.30, 0.10, 100.0),
            (2021, 0.20, 0.40, 0.18, 100.0),
            (2022, 0.20, 0.50, 0.25, 100.0),
            (2023, 0.20, 0.40, 0.15, 100.0),
        ]
    )
    stab = Stability.from_history(history)

    assert stab.gross_margin_stddev() == pytest.approx(
        statistics.stdev([0.30, 0.40, 0.50, 0.40])
    )
    assert stab.net_margin_stddev() == pytest.approx(
        statistics.stdev([0.10, 0.18, 0.25, 0.15])
    )
    # ROE is constant ⇒ stddev == 0 (NOT None), distinguishing "perfectly
    # consistent" from "insufficient data".
    assert stab.roe_stddev() == pytest.approx(0.0)


def test_earnings_cv_unitless_via_full_year_ttm() -> None:
    # Full-year NP increasing 100 -> 200 over 5 years (steady growth). The
    # TTM-at-Q4 series captures the full-year totals.
    history = _build_full_year_history(
        [
            (2020, 0.15, 0.30, 0.10, 100.0),
            (2021, 0.15, 0.30, 0.10, 125.0),
            (2022, 0.15, 0.30, 0.10, 150.0),
            (2023, 0.15, 0.30, 0.10, 175.0),
            (2024, 0.15, 0.30, 0.10, 200.0),
        ]
    )
    stab = Stability.from_history(history)

    # annual_net_profit should be the 5 full-year totals (TTM at each Q4).
    assert stab.annual_net_profit.values == pytest.approx(
        [100.0, 125.0, 150.0, 175.0, 200.0]
    )
    expected_cv = statistics.stdev(
        [100.0, 125.0, 150.0, 175.0, 200.0]
    ) / 150.0
    assert stab.earnings_coefficient_of_variation() == pytest.approx(expected_cv)


def test_earnings_growth_volatility_strips_steady_trend() -> None:
    # A perfectly smooth 25% YoY compounder should read as zero growth
    # volatility, even though its level CV is large from the upward trend.
    history = _build_full_year_history(
        [
            (2020, 0.20, 0.30, 0.10, 100.0),
            (2021, 0.20, 0.30, 0.10, 125.0),
            (2022, 0.20, 0.30, 0.10, 156.25),
            (2023, 0.20, 0.30, 0.10, 195.3125),
            (2024, 0.20, 0.30, 0.10, 244.140625),
        ]
    )
    stab = Stability.from_history(history)

    # Growth rates are all ~0.25 — perfectly stable growth (modulo the
    # 2-decimal rounding inside ``single_quarter_series`` summed via
    # ``ttm_series``, which leaves sub-percent floating noise).
    assert stab.earnings_growth_volatility() == pytest.approx(0.0, abs=1e-3)
    # Level CV is non-trivial purely from the upward trend (~0.35 here).
    assert stab.earnings_coefficient_of_variation() > 0.3


def test_earnings_growth_volatility_drops_non_positive_prior() -> None:
    # The leading prior year is negative, so the first growth rate is
    # undefined. The remaining 3 rates should drive the CV.
    history = _build_full_year_history(
        [
            (2020, 0.10, 0.30, 0.10, -50.0),
            (2021, 0.10, 0.30, 0.10, 100.0),  # prior is -50, dropped
            (2022, 0.10, 0.30, 0.10, 110.0),  # growth 10%
            (2023, 0.10, 0.30, 0.10, 121.0),  # growth 10%
            (2024, 0.10, 0.30, 0.10, 145.2),  # growth 20%
        ]
    )
    stab = Stability.from_history(history)

    # Two of three remaining growth rates are 10% and one is 20% ⇒ non-zero CV.
    assert stab.earnings_growth_volatility() is not None
    assert stab.earnings_growth_volatility() > 0


def test_earnings_cv_returns_none_when_mean_near_zero() -> None:
    # NP oscillates around zero — CV is mathematically unstable here.
    history = _build_full_year_history(
        [
            (2020, 0.0, 0.20, 0.0, 100.0),
            (2021, 0.0, 0.20, 0.0, -100.0),
            (2022, 0.0, 0.20, 0.0, 100.0),
            (2023, 0.0, 0.20, 0.0, -100.0),
        ]
    )
    stab = Stability.from_history(history)

    assert stab.earnings_coefficient_of_variation() is None


def test_stddev_returns_none_with_insufficient_points() -> None:
    history = _build_full_year_history(
        [
            (2024, 0.20, 0.40, 0.15, 100.0),
        ]
    )
    stab = Stability.from_history(history)

    assert stab.roe_stddev() is None
    assert stab.gross_margin_stddev() is None
    assert stab.net_margin_stddev() is None
    assert stab.earnings_coefficient_of_variation() is None


def test_empty_history_yields_none() -> None:
    history = FinancialHistory.of(_SYMBOL, [])
    stab = Stability.from_history(history)

    assert stab.roe_stddev() is None
    assert stab.earnings_coefficient_of_variation() is None
