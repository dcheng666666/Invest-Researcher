"""Tests for ``backend.domain.quality.cash_flow.CashFlowQuality``."""

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
from backend.domain.quality.cash_flow import CashFlowQuality
from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol


_SYMBOL = Symbol(code="00700", market=Market.HK)
# HK reports use DISCRETE with per-quarter values (fixtures mimic post-ingest
# discrete flows, not raw Eastmoney YTD cumulants).
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
    net_profit: float | None = None,
    ocf: float | None = None,
    capex: float | None = None,
    fcf: float | None = None,
) -> FinancialReport:
    return FinancialReport(
        security_id=_SYMBOL,
        period=_period(year, quarter),
        accounting=_HK_ACCOUNTING,
        income_statement=IncomeStatement(net_profit=net_profit),
        balance_sheet=BalanceSheet(),
        cash_flow_statement=CashFlowStatement(
            operating_cash_flow=ocf, capex=capex
        ),
        metrics=FinancialMetrics(free_cash_flow=fcf),
    )


def _build_history(reports: list[FinancialReport]) -> FinancialHistory:
    return FinancialHistory.of(_SYMBOL, reports)


def test_cash_flow_quality_series_population() -> None:
    history = _build_history(
        [
            _report(2023, 1, net_profit=100, ocf=80, capex=20, fcf=60),
            _report(2023, 2, net_profit=120, ocf=140, capex=30, fcf=110),
            _report(2023, 3, net_profit=110, ocf=130, capex=25, fcf=105),
            _report(2023, 4, net_profit=130, ocf=150, capex=40, fcf=110),
        ]
    )
    cf = CashFlowQuality.from_history(history)

    assert cf.free_cash_flow.values == pytest.approx([60, 110, 105, 110])
    assert cf.operating_cash_flow.values == pytest.approx([80, 140, 130, 150])
    assert cf.capex.values == pytest.approx([20, 30, 25, 40])
    assert cf.net_profit.values == pytest.approx([100, 120, 110, 130])


def test_fcf_stability_back_compat_counters() -> None:
    history = _build_history(
        [
            _report(2023, 1, fcf=-10),
            _report(2023, 2, fcf=20),
            _report(2023, 3, fcf=30),
            _report(2023, 4, fcf=-5),
        ]
    )
    cf = CashFlowQuality.from_history(history)

    # Existing evaluator still relies on these two counters.
    assert cf.total_periods == 4
    assert cf.positive_periods == 2


def test_ocf_consistency_counters_independent_of_fcf() -> None:
    # FCF can be uniformly negative (heavy capex) while OCF stays uniformly
    # positive — that's a capital-heavy printing business, NOT a broken one.
    history = _build_history(
        [
            _report(2023, 1, ocf=100, capex=120, fcf=-20),
            _report(2023, 2, ocf=110, capex=140, fcf=-30),
            _report(2023, 3, ocf=120, capex=130, fcf=-10),
            _report(2023, 4, ocf=130, capex=160, fcf=-30),
        ]
    )
    cf = CashFlowQuality.from_history(history)

    assert cf.positive_periods == 0  # FCF
    assert cf.ocf_positive_periods == 4  # OCF
    assert cf.ocf_total_periods == 4


def test_earnings_to_cash_conversion() -> None:
    history = _build_history(
        [
            _report(2023, 1, net_profit=100, ocf=120),
            _report(2023, 2, net_profit=200, ocf=180),
            _report(2023, 3, net_profit=150, ocf=180),
            _report(2023, 4, net_profit=250, ocf=270),
        ]
    )
    cf = CashFlowQuality.from_history(history)

    # Per-period series exposed for charting.
    assert cf.conversion_ratios.values == pytest.approx([1.20, 0.90, 1.20, 1.08])
    # Aggregate is sum(OCF) / sum(NP) = 750 / 700 = 1.0714, NOT mean of ratios.
    assert cf.aggregate_conversion_ratio() == pytest.approx(750 / 700)


def test_aggregate_conversion_robust_against_small_denominators() -> None:
    # The whole point of aggregate-vs-mean: a near-zero NP quarter must NOT
    # dominate the assessment-grade scalar.
    history = _build_history(
        [
            _report(2023, 1, net_profit=100, ocf=100),
            _report(2023, 2, net_profit=100, ocf=100),
            _report(2023, 3, net_profit=1, ocf=80),     # mean(ratio) would explode (80x)
            _report(2023, 4, net_profit=100, ocf=100),
        ]
    )
    cf = CashFlowQuality.from_history(history)

    # Per-period series shows the noise.
    assert max(cf.conversion_ratios.values) == pytest.approx(80.0)
    # Aggregate stays sane: 380 / 301 ≈ 1.26.
    assert cf.aggregate_conversion_ratio() == pytest.approx(380 / 301)


def test_conversion_ratio_drops_zero_or_missing_net_profit() -> None:
    history = _build_history(
        [
            _report(2023, 1, net_profit=0, ocf=100),    # zero NP -> period skipped
            _report(2023, 2, net_profit=None, ocf=80),  # missing NP -> period skipped
            _report(2023, 3, net_profit=100, ocf=120),  # only matched period
        ]
    )
    cf = CashFlowQuality.from_history(history)

    assert cf.conversion_ratios.values == pytest.approx([1.2])
    # Aggregate is period-matched: only Q3 has both OCF and non-zero NP, so
    # the OCF leaked from Q1 (where NP=0) does NOT inflate the numerator.
    assert cf.aggregate_conversion_ratio() == pytest.approx(1.2)


def test_capex_intensity() -> None:
    history = _build_history(
        [
            _report(2023, 1, ocf=100, capex=20),
            _report(2023, 2, ocf=200, capex=40),
            _report(2023, 3, ocf=100, capex=80),
            _report(2023, 4, ocf=300, capex=60),
        ]
    )
    cf = CashFlowQuality.from_history(history)

    assert cf.capex_intensity_ratios.values == pytest.approx([0.2, 0.2, 0.8, 0.2])
    # Aggregate: 200 / 700 = 0.2857, not mean(0.35).
    assert cf.aggregate_capex_intensity() == pytest.approx(200 / 700)


def test_capex_intensity_skips_periods_with_zero_or_missing_ocf() -> None:
    history = _build_history(
        [
            _report(2023, 1, ocf=0, capex=20),     # zero OCF -> period skipped
            _report(2023, 2, ocf=None, capex=40),  # missing OCF -> period skipped
            _report(2023, 3, ocf=100, capex=30),   # only matched period
        ]
    )
    cf = CashFlowQuality.from_history(history)

    assert cf.capex_intensity_ratios.values == pytest.approx([0.3])
    # Period-matched: the zero-OCF Q1 capex of 20 and the missing-OCF Q2
    # capex of 40 are both excluded so they cannot leak into the numerator.
    assert cf.aggregate_capex_intensity() == pytest.approx(0.3)


def test_empty_history_yields_none_summaries() -> None:
    history = _build_history([])
    cf = CashFlowQuality.from_history(history)

    assert cf.total_periods == 0
    assert cf.positive_periods == 0
    assert cf.ocf_total_periods == 0
    assert cf.aggregate_conversion_ratio() is None
    assert cf.aggregate_capex_intensity() is None
