"""Tests for ``backend.repositories.financial_repository``.

The A-share path does the heavy lifting in the repository itself: three
THS DataFrames (financial abstract / indicator / cash flow) are aligned
by ``ReportPeriod`` and folded into a single ``FinancialReport`` per
period. The HK path delegates to ``eastmoney_hk.fetch_reports_hk`` which
already returns ``FinancialReport`` objects.

Mocks here mirror the actual upstream shapes so the contract between
repository and source layer stays explicit:

A-share (THS):
- ``fetch_financial_abstract``: columns ``报告期`` (e.g. "2023-12-31"),
  ``营业总收入`` / ``净利润`` / ``扣非净利润`` (Chinese-formatted strings
  like "1505.39亿"), ``基本每股收益`` (string yuan/share), plus six ratio
  columns suffixed with ``%`` and the two plain-multiple liquidity ratios
  ``流动比率`` / ``速动比率``.
- ``fetch_financial_indicator``: columns ``日期`` (already converted to
  Timestamp at the source layer), ``三项费用比重`` ("10.32%"), turnover-day
  floats, ``总资产(元)`` (raw yuan float), and the two plain-percent
  fields ``总资产净利润率(%)`` / ``现金比率(%)``.
- ``fetch_cash_flow``: columns ``报告期``, ``*经营活动产生的现金流量净额``,
  ``购建固定资产、无形资产和其他长期资产支付的现金``.

HK: ``fetch_reports_hk(code, window_years) -> list[FinancialReport]``.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.domain.financials.accounting import (
    AccountingContext,
    PeriodPresentation,
    ReportingStandard,
)
from backend.domain.financials.metrics import FinancialMetrics
from backend.domain.financials.period import ReportPeriod
from backend.domain.financials.report import FinancialReport
from backend.domain.financials.statements import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
)
from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol
from backend.repositories import financial_repository


# --------------------------------------------------------------------------- #
# A-share path: three THS DataFrames composed by report period
# --------------------------------------------------------------------------- #


def _patch_a_share_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    *,
    abstract: pd.DataFrame,
    indicator: pd.DataFrame,
    cash_flow: pd.DataFrame,
) -> None:
    monkeypatch.setattr(
        financial_repository.ths_a_share,
        "fetch_financial_abstract",
        lambda code, window_years=None: abstract,
    )
    monkeypatch.setattr(
        financial_repository.ths_a_share,
        "fetch_financial_indicator",
        lambda code, window_years=None: indicator,
    )
    monkeypatch.setattr(
        financial_repository.ths_a_share,
        "fetch_cash_flow",
        lambda code, window_years=None: cash_flow,
    )


def _abstract_row_2023_q4() -> dict:
    return {
        "报告期": "2023-12-31",
        "营业总收入": "1505.39亿",
        "净利润": "747.34亿",
        "扣非净利润": "747.55亿",
        "基本每股收益": "59.49",
        "销售毛利率": "92.06%",
        "销售净利率": "53.42%",
        "净资产收益率": "34.19%",
        "营业总收入同比增长率": "18.04%",
        "扣非净利润同比增长率": "19.16%",
        "资产负债率": "16.81%",
        "流动比率": "6.62",
        "速动比率": "5.99",
    }


def _indicator_row_2023_q4() -> dict:
    """``日期`` is Timestamp because ``fetch_financial_indicator`` calls
    ``df["日期"] = pd.to_datetime(df["日期"])`` before returning.
    """
    return {
        "日期": pd.Timestamp("2023-12-31"),
        "三项费用比重": "10.32%",
        "应收账款周转天数(天)": 0.5,
        "存货周转天数(天)": 350.2,
        "总资产(元)": 234_000_000_000.0,
        "总资产净利润率(%)": 28.62,
        "现金比率(%)": 145.6,
    }


def _cash_flow_row_2023_q4() -> dict:
    return {
        "报告期": "2023-12-31",
        "*经营活动产生的现金流量净额": "665.55亿",
        "购建固定资产、无形资产和其他长期资产支付的现金": "26.72亿",
    }


def test_get_financial_history_a_share_full_row_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One period that appears in all three endpoints exercises every
    mapping branch: number unit parsing, percent decimal conversion,
    ROA / cash-ratio /100 normalisation, and balance-sheet back-derivation
    via ``total_assets * debt_ratio``.
    """
    _patch_a_share_endpoints(
        monkeypatch,
        abstract=pd.DataFrame([_abstract_row_2023_q4()]),
        indicator=pd.DataFrame([_indicator_row_2023_q4()]),
        cash_flow=pd.DataFrame([_cash_flow_row_2023_q4()]),
    )

    history = financial_repository.get_financial_history("600519")

    assert history.security_id == Symbol(code="600519", market=Market.A)
    assert len(history.reports) == 1
    report = history.reports[0]

    assert report.period == ReportPeriod.quarterly(2023, 4, date(2023, 12, 31))
    assert report.accounting == AccountingContext(
        currency="CNY",
        standard=ReportingStandard.CAS,
        period_presentation=PeriodPresentation.YTD_CUMULATIVE,
    )

    income = report.income_statement
    assert income.revenue == pytest.approx(1505.39 * 1e8)
    assert income.net_profit == pytest.approx(747.34 * 1e8)
    assert income.net_profit_deducted == pytest.approx(747.55 * 1e8)
    assert income.eps == pytest.approx(59.49)

    # total_liabilities = total_assets * debt_ratio (back-derived because
    # THS does not publish absolute liabilities in either endpoint).
    balance = report.balance_sheet
    assert balance.total_assets == pytest.approx(234_000_000_000.0)
    assert balance.total_liabilities == pytest.approx(
        234_000_000_000.0 * 0.1681
    )
    assert balance.total_equity == pytest.approx(
        234_000_000_000.0 * (1 - 0.1681)
    )

    cashflow = report.cash_flow_statement
    assert cashflow.operating_cash_flow == pytest.approx(665.55 * 1e8)
    assert cashflow.capex == pytest.approx(26.72 * 1e8)

    metrics = report.metrics
    assert metrics.gross_margin == pytest.approx(0.9206)
    assert metrics.net_margin == pytest.approx(0.5342)
    assert metrics.roe == pytest.approx(0.3419)
    assert metrics.roa == pytest.approx(0.2862)  # 28.62 / 100
    assert metrics.debt_ratio == pytest.approx(0.1681)
    assert metrics.current_ratio == pytest.approx(6.62)
    assert metrics.quick_ratio == pytest.approx(5.99)
    assert metrics.cash_ratio == pytest.approx(1.456)  # 145.6 / 100
    assert metrics.revenue_growth == pytest.approx(0.1804)
    assert metrics.profit_growth == pytest.approx(0.1916)
    assert metrics.receivable_turnover_days == pytest.approx(0.5)
    assert metrics.inventory_turnover_days == pytest.approx(350.2)
    assert metrics.selling_expense_ratio == pytest.approx(0.1032)
    assert metrics.free_cash_flow == pytest.approx(
        665.55 * 1e8 - 26.72 * 1e8
    )


def test_get_financial_history_a_share_period_only_in_abstract_yields_partial_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the indicator and cash-flow endpoints lack the abstract's period,
    BalanceSheet / CashFlowStatement stay empty and FCF / ROA fall back to
    None (ROA fallback to net_profit/total_assets cannot fire because
    total_assets is unavailable here).
    """
    _patch_a_share_endpoints(
        monkeypatch,
        abstract=pd.DataFrame([_abstract_row_2023_q4()]),
        indicator=pd.DataFrame(),
        cash_flow=pd.DataFrame(),
    )

    history = financial_repository.get_financial_history("600519")
    report = history.reports[0]

    assert report.balance_sheet == BalanceSheet()
    assert report.cash_flow_statement == CashFlowStatement()

    metrics = report.metrics
    # Ratios that come from the abstract still populate.
    assert metrics.gross_margin == pytest.approx(0.9206)
    assert metrics.debt_ratio == pytest.approx(0.1681)
    # Indicator-only ratios stay None.
    assert metrics.roa is None
    assert metrics.cash_ratio is None
    assert metrics.receivable_turnover_days is None
    # FCF requires both OCF and capex.
    assert metrics.free_cash_flow is None


def test_get_financial_history_a_share_indicator_only_periods_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Periods that show up in the indicator endpoint but not in the
    abstract are intentionally dropped; the abstract is the canonical
    period spine."""
    abstract = pd.DataFrame([_abstract_row_2023_q4()])
    indicator = pd.DataFrame(
        [
            _indicator_row_2023_q4(),
            # An extra period the abstract never reports — must be ignored.
            {
                "日期": pd.Timestamp("2024-06-30"),
                "三项费用比重": "11.00%",
                "应收账款周转天数(天)": 1.0,
                "存货周转天数(天)": 360.0,
                "总资产(元)": 250_000_000_000.0,
                "总资产净利润率(%)": 14.0,
                "现金比率(%)": 90.0,
            },
        ]
    )
    cash_flow = pd.DataFrame([_cash_flow_row_2023_q4()])
    _patch_a_share_endpoints(
        monkeypatch, abstract=abstract, indicator=indicator, cash_flow=cash_flow
    )

    history = financial_repository.get_financial_history("600519")
    assert [r.period.label for r in history.reports] == ["2023Q4"]


def test_get_financial_history_a_share_returns_empty_history_on_empty_abstract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_a_share_endpoints(
        monkeypatch,
        abstract=pd.DataFrame(),
        indicator=pd.DataFrame(),
        cash_flow=pd.DataFrame(),
    )

    history = financial_repository.get_financial_history("600519")

    assert history.security_id == Symbol(code="600519", market=Market.A)
    assert history.has_data() is False
    assert history.reports == ()


def test_get_financial_history_a_share_skips_rows_with_unparseable_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``报告期`` values that are not quarter-end dates (e.g. 2023-05-31)
    cannot be mapped to a ``ReportPeriod`` and are silently skipped at the
    abstract level."""
    bad_row = _abstract_row_2023_q4() | {"报告期": "2023-05-31"}
    abstract = pd.DataFrame([bad_row, _abstract_row_2023_q4()])
    _patch_a_share_endpoints(
        monkeypatch,
        abstract=abstract,
        indicator=pd.DataFrame([_indicator_row_2023_q4()]),
        cash_flow=pd.DataFrame([_cash_flow_row_2023_q4()]),
    )

    history = financial_repository.get_financial_history("600519")
    assert [r.period.label for r in history.reports] == ["2023Q4"]


def test_get_financial_history_a_share_falls_back_to_computed_roa_when_indicator_missing_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the indicator row supplies ``总资产(元)`` but no
    ``总资产净利润率(%)``, ``FinancialMetrics.derive`` falls back to
    ``net_profit / total_assets`` so the back-derived balance sheet
    becomes the source of truth for ROA.
    """
    indicator_no_roa = _indicator_row_2023_q4()
    indicator_no_roa["总资产净利润率(%)"] = None
    _patch_a_share_endpoints(
        monkeypatch,
        abstract=pd.DataFrame([_abstract_row_2023_q4()]),
        indicator=pd.DataFrame([indicator_no_roa]),
        cash_flow=pd.DataFrame([_cash_flow_row_2023_q4()]),
    )

    history = financial_repository.get_financial_history("600519")
    metrics = history.reports[0].metrics

    expected_roa = (747.34 * 1e8) / 234_000_000_000.0
    assert metrics.roa == pytest.approx(expected_roa)


# --------------------------------------------------------------------------- #
# HK path: eastmoney_hk.fetch_reports_hk passthrough
# --------------------------------------------------------------------------- #


def _hk_report(year: int, quarter: int, period_end: date) -> FinancialReport:
    return FinancialReport(
        security_id=Symbol(code="00700", market=Market.HK),
        period=ReportPeriod.quarterly(year, quarter, period_end),
        accounting=AccountingContext(
            currency="HKD",
            standard=ReportingStandard.IFRS,
            period_presentation=PeriodPresentation.DISCRETE,
        ),
        income_statement=IncomeStatement(
            revenue=600_000_000_000.0,
            net_profit=160_000_000_000.0,
            net_profit_deducted=160_000_000_000.0,
            eps=17.4,
        ),
        balance_sheet=BalanceSheet(),
        cash_flow_statement=CashFlowStatement(
            operating_cash_flow=220_000_000_000.0,
            capex=80_000_000_000.0,
        ),
        metrics=FinancialMetrics(
            gross_margin=0.5,
            net_margin=0.27,
            roe=0.22,
            roa=0.12,
            debt_ratio=0.45,
            current_ratio=1.4,
            revenue_growth=0.10,
            profit_growth=0.20,
            free_cash_flow=140_000_000_000.0,
        ),
    )


def test_get_financial_history_hk_delegates_to_source_and_wraps_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """For HK the source layer already returns ready ``FinancialReport``
    objects; the repository's job is to validate them under
    ``FinancialHistory.of`` (chronological order, single presentation)
    and stamp the right ``security_id``.
    """
    reports = [
        _hk_report(2022, 4, date(2022, 12, 31)),
        _hk_report(2023, 4, date(2023, 12, 31)),
    ]

    captured: dict = {}

    def fake_fetch(code, window_years):
        captured["code"] = code
        captured["window_years"] = window_years
        return reports

    monkeypatch.setattr(
        financial_repository.eastmoney_hk, "fetch_reports_hk", fake_fetch
    )

    history = financial_repository.get_financial_history("HK00700", window_years=5)

    assert captured == {"code": "00700", "window_years": 5}
    assert history.security_id == Symbol(code="00700", market=Market.HK)
    assert [r.period.label for r in history.reports] == ["2022Q4", "2023Q4"]
    assert all(
        r.accounting.standard is ReportingStandard.IFRS for r in history.reports
    )


def test_get_financial_history_hk_returns_empty_when_source_yields_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        financial_repository.eastmoney_hk,
        "fetch_reports_hk",
        lambda code, window_years: [],
    )

    history = financial_repository.get_financial_history("HK00700")

    assert history.security_id == Symbol(code="00700", market=Market.HK)
    assert history.has_data() is False
    assert history.reports == ()
