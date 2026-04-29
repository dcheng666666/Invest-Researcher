"""Tests for ``backend.domain.quality.profitability``."""

from __future__ import annotations

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
from backend.domain.quality.profitability import (
    GrossMargin,
    NetMargin,
    Profitability,
    ReturnOnAssets,
    ReturnOnEquity,
)
from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol


_ACCOUNTING = AccountingContext(
    currency="CNY",
    standard=ReportingStandard.CAS,
    period_presentation=PeriodPresentation.YTD_CUMULATIVE,
)

_SYMBOL = Symbol(code="600519", market=Market.A)


def _annual_period(year: int) -> ReportPeriod:
    return ReportPeriod.quarterly(year, 4, date(year, 12, 31))


def _annual_report(year: int, metrics: FinancialMetrics) -> FinancialReport:
    return FinancialReport(
        security_id=_SYMBOL,
        period=_annual_period(year),
        accounting=_ACCOUNTING,
        income_statement=IncomeStatement(),
        balance_sheet=BalanceSheet(),
        cash_flow_statement=CashFlowStatement(),
        metrics=metrics,
    )


def _build_history(years: int = 5) -> FinancialHistory:
    """Three-year ramp of ROE / ROA / margins for shape assertions."""
    samples = [
        # (roe, roa, gross_margin, net_margin)
        (0.10, 0.05, 0.30, 0.10),
        (0.15, 0.07, 0.32, 0.12),
        (0.20, 0.09, 0.34, 0.14),
        (0.18, 0.08, 0.36, 0.16),
        (0.22, 0.10, 0.38, 0.18),
    ]
    reports = [
        _annual_report(
            2020 + i,
            FinancialMetrics(
                roe=roe, roa=roa, gross_margin=gm, net_margin=nm
            ),
        )
        for i, (roe, roa, gm, nm) in enumerate(samples[:years])
    ]
    return FinancialHistory.of(_SYMBOL, reports)


def test_return_on_equity_helpers() -> None:
    history = _build_history(5)
    roe = ReturnOnEquity.from_history(history)

    assert roe.annual_period_count() == 5
    assert roe.latest() == pytest.approx(0.22)
    assert roe.average(annual_only=True) == pytest.approx(0.17)
    # 4 of 5 years above 15% (the 0.10 entry is below).
    assert roe.years_above(0.15) == 4


def test_return_on_assets_built_from_history() -> None:
    history = _build_history(3)
    roa = ReturnOnAssets.from_history(history)

    assert isinstance(roa, ReturnOnAssets)
    assert roa.quarterly.values == pytest.approx([0.05, 0.07, 0.09])
    assert roa.latest() == pytest.approx(0.09)
    assert roa.average() == pytest.approx(0.07)


def test_gross_and_net_margin_built_from_history() -> None:
    history = _build_history(4)
    gm = GrossMargin.from_history(history)
    nm = NetMargin.from_history(history)

    assert gm.quarterly.values == pytest.approx([0.30, 0.32, 0.34, 0.36])
    assert nm.quarterly.values == pytest.approx([0.10, 0.12, 0.14, 0.16])
    # Margins typically improve over time in this fixture; latest > average.
    assert gm.latest() > gm.average()
    assert nm.latest() > nm.average()


def test_profitability_aggregates_four_ratios() -> None:
    history = _build_history(5)
    profitability = Profitability.from_history(history)

    assert isinstance(profitability.roe, ReturnOnEquity)
    assert isinstance(profitability.roa, ReturnOnAssets)
    assert isinstance(profitability.gross_margin, GrossMargin)
    assert isinstance(profitability.net_margin, NetMargin)

    # Sanity-check pass-through to each sub-VO.
    assert profitability.roe.average() == pytest.approx(0.17)
    assert profitability.roa.average() == pytest.approx(0.078)
    assert profitability.gross_margin.latest() == pytest.approx(0.38)
    assert profitability.net_margin.latest() == pytest.approx(0.18)


def test_profitability_handles_missing_metrics() -> None:
    # When a feed (e.g. HK) leaves ROA as None on every report, the resulting
    # series is empty rather than raising. ROE etc. should still populate.
    reports = [
        _annual_report(
            2023, FinancialMetrics(roe=0.18, roa=None, gross_margin=0.4, net_margin=0.2)
        ),
        _annual_report(
            2024, FinancialMetrics(roe=0.20, roa=None, gross_margin=0.42, net_margin=0.22)
        ),
    ]
    history = FinancialHistory.of(_SYMBOL, reports)

    profitability = Profitability.from_history(history)

    assert profitability.roe.annual_period_count() == 2
    assert profitability.roa.annual_period_count() == 0
    assert profitability.roa.latest() is None
    assert profitability.roa.average() is None
    assert profitability.gross_margin.latest() == pytest.approx(0.42)
