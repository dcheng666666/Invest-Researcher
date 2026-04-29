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
from backend.domain.financials.series import FinancialSeries
from backend.domain.financials.statements import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
)
from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol
from backend.domain.valuation.history import ttm_profit_timeline_from_history


def _period(year: int, quarter: int) -> ReportPeriod:
    month_day = {
        1: (3, 31),
        2: (6, 30),
        3: (9, 30),
        4: (12, 31),
    }
    month, day = month_day[quarter]
    return ReportPeriod.quarterly(year, quarter, date(year, month, day))


def _report(
    symbol: Symbol,
    year: int,
    quarter: int,
    *,
    presentation: PeriodPresentation = PeriodPresentation.YTD_CUMULATIVE,
    revenue: float | None = None,
    net_profit: float | None = None,
    net_profit_deducted: float | None = None,
    eps: float | None = None,
    ocf: float | None = None,
    capex: float | None = None,
    metrics: FinancialMetrics | None = None,
) -> FinancialReport:
    return FinancialReport(
        security_id=symbol,
        period=_period(year, quarter),
        accounting=AccountingContext(
            currency="CNY",
            standard=ReportingStandard.CAS,
            period_presentation=presentation,
        ),
        income_statement=IncomeStatement(
            revenue=revenue,
            net_profit=net_profit,
            net_profit_deducted=net_profit_deducted,
            eps=eps,
        ),
        balance_sheet=BalanceSheet(
            total_assets=1000.0,
            total_liabilities=400.0,
            total_equity=600.0,
        ),
        cash_flow_statement=CashFlowStatement(
            operating_cash_flow=ocf,
            capex=capex,
        ),
        metrics=metrics or FinancialMetrics(),
    )


def test_report_period() -> None:
    p = ReportPeriod.quarterly(2024, 4, date(2024, 12, 31))
    assert p.label == "2024Q4"
    assert p.is_annual is True
    assert str(p) == "2024Q4"

    p2 = ReportPeriod.quarterly(2025, 4, date(2025, 12, 31))
    assert p.years_until(p2) == pytest.approx(1.0, rel=0.01)
    assert p < p2

    with pytest.raises(ValueError):
        ReportPeriod.quarterly(2024, 5, date(2024, 12, 31))


def test_financial_series_of_filters_invalid_values() -> None:
    p1, p2, p3, p4 = _period(2024, 1), _period(2024, 2), _period(2024, 3), _period(2024, 4)
    series = FinancialSeries.of(
        [
            (p1, 10),
            (p2, None),
            (p3, "oops"),
            (p4, float("nan")),
        ]
    )

    assert list(series) == [(p1, 10.0)]
    assert len(series) == 1
    assert bool(series) is True


def test_financial_series_helpers() -> None:
    p1, p2, p3 = _period(2022, 4), _period(2023, 4), _period(2024, 4)
    series = FinancialSeries.of([(p1, 100), (p2, 110), (p3, 121)])

    assert series.values == [100.0, 110.0, 121.0]
    assert series.periods == [p1, p2, p3]
    assert series.latest() == (p3, 121.0)
    assert series.latest_n(2).pairs == ((p2, 110.0), (p3, 121.0))
    assert series.annual_only().pairs == series.pairs


def test_financial_series_cagr() -> None:
    p1, p2, p3 = _period(2022, 4), _period(2023, 4), _period(2024, 4)
    series = FinancialSeries.of([(p1, 100), (p2, 110), (p3, 121)])

    assert series.cagr() == pytest.approx(0.1, rel=0.01)

    sign_flip = FinancialSeries.of([(p1, -100), (p3, 20)])
    assert sign_flip.cagr() == pytest.approx(0.6, rel=0.05)
    assert FinancialSeries.of([(p1, 100)]).cagr() is None


def test_financial_metrics_derive() -> None:
    upstream = FinancialMetrics(gross_margin=0.3, net_margin=0.2)
    metrics = FinancialMetrics.derive(
        IncomeStatement(revenue=1000, net_profit=200),
        BalanceSheet(total_assets=1000, total_liabilities=400, total_equity=600),
        CashFlowStatement(operating_cash_flow=150, capex=40),
        upstream=upstream,
    )
    assert metrics.gross_margin == 0.3
    assert metrics.net_margin == 0.2
    assert metrics.free_cash_flow == 110
    # ROA falls back to net_profit / total_assets when upstream omits it.
    assert metrics.roa == pytest.approx(0.2)

    with_upstream_fcf = FinancialMetrics.derive(
        IncomeStatement(),
        BalanceSheet(),
        CashFlowStatement(operating_cash_flow=200, capex=30),
        upstream=FinancialMetrics(free_cash_flow=999),
    )
    assert with_upstream_fcf.free_cash_flow == 999


def test_financial_metrics_derive_roa_prefers_upstream() -> None:
    # Upstream-supplied ROA (e.g. THS 总资产净利润率 / Eastmoney HK ROA) wins
    # over local derivation, mirroring the FCF/ROE precedence pattern.
    metrics = FinancialMetrics.derive(
        IncomeStatement(net_profit=200),
        BalanceSheet(total_assets=1000),
        CashFlowStatement(),
        upstream=FinancialMetrics(roa=0.123),
    )
    assert metrics.roa == 0.123


def test_financial_metrics_derive_roa_none_when_inputs_missing() -> None:
    # No upstream ROA + missing balance sheet -> stays None instead of raising.
    metrics = FinancialMetrics.derive(
        IncomeStatement(net_profit=200),
        BalanceSheet(),
        CashFlowStatement(),
    )
    assert metrics.roa is None

    # Net profit known but total_assets is None (HK case) -> still None.
    hk_like = FinancialMetrics.derive(
        IncomeStatement(net_profit=200),
        BalanceSheet(total_assets=None),
        CashFlowStatement(),
    )
    assert hk_like.roa is None

    # total_assets == 0 must not raise ZeroDivisionError.
    zero_assets = FinancialMetrics.derive(
        IncomeStatement(net_profit=200),
        BalanceSheet(total_assets=0.0),
        CashFlowStatement(),
    )
    assert zero_assets.roa is None


def test_financial_report_identity_property() -> None:
    symbol = Symbol(code="600519", market=Market.A)
    report = _report(symbol, 2024, 4)
    assert report.identity == (symbol, _period(2024, 4))


def test_financial_history_invariants_and_factories() -> None:
    symbol = Symbol(code="600519", market=Market.A)
    r2 = _report(symbol, 2024, 2)
    r1 = _report(symbol, 2024, 1)
    history = FinancialHistory.of(symbol, [r2, r1])
    assert history.reports == (r1, r2)

    wrong_symbol = Symbol(code="00700", market=Market.HK)
    with pytest.raises(ValueError):
        FinancialHistory(security_id=symbol, reports=(r1, _report(wrong_symbol, 2024, 2)))

    with pytest.raises(ValueError):
        FinancialHistory(security_id=symbol, reports=(r2, r1))

    with pytest.raises(ValueError):
        FinancialHistory(
            security_id=symbol,
            reports=(
                _report(symbol, 2024, 1, presentation=PeriodPresentation.YTD_CUMULATIVE),
                _report(symbol, 2024, 2, presentation=PeriodPresentation.DISCRETE),
            ),
        )


def test_financial_history_basic_accessors_and_series() -> None:
    symbol = Symbol(code="600519", market=Market.A)
    r1 = _report(
        symbol,
        2023,
        4,
        revenue=100,
        net_profit_deducted=80,
        eps=-0.2,
        ocf=120,
        capex=20,
        metrics=FinancialMetrics(gross_margin=0.35),
    )
    r2 = _report(
        symbol,
        2024,
        4,
        revenue=121,
        net_profit_deducted=95,
        eps=1.23,
        ocf=140,
        capex=25,
        metrics=FinancialMetrics(gross_margin=0.4),
    )
    history = FinancialHistory.of(symbol, [r1, r2])

    assert history.has_data() is True

    assert history.series_for("revenue").values == [100.0, 121.0]
    assert history.income_series("revenue").values == [100.0, 121.0]
    assert history.metric_series("gross_margin").values == [0.35, 0.4]


def test_financial_history_single_quarter_series_for_ytd_and_discrete() -> None:
    symbol = Symbol(code="600519", market=Market.A)
    ytd = FinancialHistory.of(
        symbol,
        [
            _report(symbol, 2024, 1, revenue=10),
            _report(symbol, 2024, 2, revenue=30),
            _report(symbol, 2024, 3, revenue=60),
            _report(symbol, 2024, 4, revenue=100),
        ],
    )
    discrete = FinancialHistory.of(
        symbol,
        [
            _report(symbol, 2024, 1, presentation=PeriodPresentation.DISCRETE, revenue=10),
            _report(symbol, 2024, 2, presentation=PeriodPresentation.DISCRETE, revenue=20),
            _report(symbol, 2024, 3, presentation=PeriodPresentation.DISCRETE, revenue=30),
        ],
    )

    assert ytd.single_quarter_series("revenue").values == [10.0, 20.0, 30.0, 40.0]
    assert discrete.single_quarter_series("revenue").values == [10.0, 20.0, 30.0]


def test_financial_history_ttm_series_and_valuation_timeline_adapter() -> None:
    symbol = Symbol(code="600519", market=Market.A)
    history = FinancialHistory.of(
        symbol,
        [
            _report(symbol, 2023, 1, net_profit_deducted=10),
            _report(symbol, 2023, 2, net_profit_deducted=30),
            _report(symbol, 2023, 3, net_profit_deducted=60),
            _report(symbol, 2023, 4, net_profit_deducted=100),
            _report(symbol, 2024, 1, net_profit_deducted=12),
            _report(symbol, 2024, 2, net_profit_deducted=34),
            _report(symbol, 2024, 3, net_profit_deducted=66),
            _report(symbol, 2024, 4, net_profit_deducted=110),
        ],
    )
    
    ttm_values = history.ttm_series("net_profit_deducted").values
    assert ttm_values == [100.0, 102.0, 104.0, 106.0, 110.0]
    assert ttm_profit_timeline_from_history(history) == [
        ("2023-12", 100.0),
        ("2024-03", 102.0),
        ("2024-06", 104.0),
        ("2024-09", 106.0),
        ("2024-12", 110.0),
    ]
