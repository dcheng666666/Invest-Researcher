"""Tests for the QualitySignal catalog + QualityAssessment aggregation.

Each signal builder is exercised at PASS / WARN / FAIL / NOT_EVALUATED
boundaries, then the assessment-level verdict mapping is verified end-to-end
via synthetic signal tuples.
"""

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
from backend.domain.quality.assessment import QualityAssessment
from backend.domain.quality.cash_flow import CashFlowQuality
from backend.domain.quality.evaluator import QualityEvaluator
from backend.domain.quality.health import FinancialHealth
from backend.domain.quality.profitability import Profitability
from backend.domain.quality.signals import (
    CORE_QUALITY_SIGNAL_BUILDERS,
    DEFAULT_SIGNAL_BUILDERS,
    QualityContext,
    QualitySignal,
    SignalStatus,
    capital_light,
    earnings_cash_backed,
    fcf_long_term_positive,
    high_gross_margin,
    liquidity_current,
    liquidity_quick,
    long_term_roe,
    low_leverage,
    ocf_consistency,
    roa_quality,
    stable_earnings_growth,
    stable_gross_margin,
    stable_roe,
)
from backend.domain.quality.stability import Stability
from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol
from backend.domain.verdict import Verdict


_SYMBOL = Symbol(code="00700", market=Market.HK)
_HK_ACCOUNTING = AccountingContext(
    currency="HKD",
    standard=ReportingStandard.IFRS,
    period_presentation=PeriodPresentation.DISCRETE,
)


def _period(year: int, quarter: int) -> ReportPeriod:
    month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    month, day = month_day[quarter]
    return ReportPeriod.quarterly(year, quarter, date(year, month, day))


def _annual_report(
    year: int,
    *,
    roe: float | None = None,
    roa: float | None = None,
    gross_margin: float | None = None,
    net_margin: float | None = None,
    debt_ratio: float | None = None,
    current_ratio: float | None = None,
    quick_ratio: float | None = None,
    cash_ratio: float | None = None,
    net_profit: float | None = None,
    ocf: float | None = None,
    capex: float | None = None,
    fcf: float | None = None,
) -> FinancialReport:
    return FinancialReport(
        security_id=_SYMBOL,
        period=_period(year, 4),
        accounting=_HK_ACCOUNTING,
        income_statement=IncomeStatement(net_profit=net_profit),
        balance_sheet=BalanceSheet(),
        cash_flow_statement=CashFlowStatement(
            operating_cash_flow=ocf, capex=capex
        ),
        metrics=FinancialMetrics(
            roe=roe,
            roa=roa,
            gross_margin=gross_margin,
            net_margin=net_margin,
            debt_ratio=debt_ratio,
            current_ratio=current_ratio,
            quick_ratio=quick_ratio,
            cash_ratio=cash_ratio,
            free_cash_flow=fcf,
        ),
    )


def _full_year_reports(
    year: int,
    *,
    net_profit_full_year: float,
    roe: float = 0.0,
    gross_margin: float = 0.0,
    net_margin: float = 0.0,
) -> list[FinancialReport]:
    """Build 4 quarterly DISCRETE reports for a year so that ``ttm_series``
    has the full window required (Q1+Q2+Q3+Q4) at each Q4 boundary."""
    per_quarter_np = net_profit_full_year / 4.0
    reports: list[FinancialReport] = []
    for q in range(1, 5):
        reports.append(
            FinancialReport(
                security_id=_SYMBOL,
                period=_period(year, q),
                accounting=_HK_ACCOUNTING,
                income_statement=IncomeStatement(net_profit=per_quarter_np),
                balance_sheet=BalanceSheet(),
                cash_flow_statement=CashFlowStatement(),
                metrics=FinancialMetrics(
                    roe=roe, gross_margin=gross_margin, net_margin=net_margin
                ),
            )
        )
    return reports


def _ctx_for(reports: list[FinancialReport]) -> QualityContext:
    history = FinancialHistory.of(_SYMBOL, reports)
    return QualityContext(
        profitability=Profitability.from_history(history),
        cash_flow=CashFlowQuality.from_history(history),
        stability=Stability.from_history(history),
        health=FinancialHealth.from_history(history),
    )


# ====================================================================== #
# Per-signal boundary tests
# ====================================================================== #


def test_long_term_roe_pass_warn_fail_and_na() -> None:
    pass_reports = [
        _annual_report(y, roe=0.20) for y in range(2018, 2024)
    ]
    warn_reports = [
        _annual_report(y, roe=0.12) for y in range(2018, 2024)
    ]
    fail_reports = [
        _annual_report(y, roe=0.05) for y in range(2018, 2024)
    ]

    assert long_term_roe(_ctx_for(pass_reports)).status is SignalStatus.PASS
    assert long_term_roe(_ctx_for(warn_reports)).status is SignalStatus.WARN
    assert long_term_roe(_ctx_for(fail_reports)).status is SignalStatus.FAIL
    assert (
        long_term_roe(_ctx_for([])).status is SignalStatus.NOT_EVALUATED
    )


def test_roa_quality_thresholds() -> None:
    assert roa_quality(_ctx_for([_annual_report(y, roa=0.10) for y in range(2018, 2024)])).status is SignalStatus.PASS
    assert roa_quality(_ctx_for([_annual_report(y, roa=0.05) for y in range(2018, 2024)])).status is SignalStatus.WARN
    assert roa_quality(_ctx_for([_annual_report(y, roa=0.02) for y in range(2018, 2024)])).status is SignalStatus.FAIL
    assert roa_quality(_ctx_for([])).status is SignalStatus.NOT_EVALUATED


def test_high_gross_margin_thresholds() -> None:
    assert high_gross_margin(_ctx_for([_annual_report(y, gross_margin=0.50) for y in range(2018, 2024)])).status is SignalStatus.PASS
    assert high_gross_margin(_ctx_for([_annual_report(y, gross_margin=0.30) for y in range(2018, 2024)])).status is SignalStatus.WARN
    assert high_gross_margin(_ctx_for([_annual_report(y, gross_margin=0.15) for y in range(2018, 2024)])).status is SignalStatus.FAIL


def test_fcf_long_term_positive_thresholds() -> None:
    pass_reports = [_annual_report(y, fcf=10) for y in range(2018, 2025)]
    sig = fcf_long_term_positive(_ctx_for(pass_reports))
    assert sig.status is SignalStatus.PASS

    warn_reports = (
        [_annual_report(y, fcf=10) for y in range(2018, 2022)]
        + [_annual_report(y, fcf=-5) for y in range(2022, 2025)]
    )
    assert fcf_long_term_positive(_ctx_for(warn_reports)).status is SignalStatus.WARN

    fail_reports = [_annual_report(y, fcf=-10) for y in range(2018, 2025)]
    assert fcf_long_term_positive(_ctx_for(fail_reports)).status is SignalStatus.FAIL

    assert fcf_long_term_positive(_ctx_for([])).status is SignalStatus.NOT_EVALUATED


def test_ocf_consistency_thresholds() -> None:
    pass_reports = [_annual_report(y, ocf=10) for y in range(2018, 2024)]
    assert ocf_consistency(_ctx_for(pass_reports)).status is SignalStatus.PASS

    fail_reports = [_annual_report(y, ocf=-1) for y in range(2018, 2024)]
    assert ocf_consistency(_ctx_for(fail_reports)).status is SignalStatus.FAIL


def test_earnings_cash_backed_thresholds() -> None:
    pass_reports = [_annual_report(y, net_profit=100, ocf=120) for y in range(2018, 2023)]
    assert earnings_cash_backed(_ctx_for(pass_reports)).status is SignalStatus.PASS

    warn_reports = [_annual_report(y, net_profit=100, ocf=60) for y in range(2018, 2023)]
    assert earnings_cash_backed(_ctx_for(warn_reports)).status is SignalStatus.WARN

    fail_reports = [_annual_report(y, net_profit=100, ocf=20) for y in range(2018, 2023)]
    assert earnings_cash_backed(_ctx_for(fail_reports)).status is SignalStatus.FAIL


def test_capital_light_inverse_threshold() -> None:
    # Light: capex/OCF small.
    light = [_annual_report(y, ocf=100, capex=20) for y in range(2018, 2023)]
    assert capital_light(_ctx_for(light)).status is SignalStatus.PASS

    medium = [_annual_report(y, ocf=100, capex=50) for y in range(2018, 2023)]
    assert capital_light(_ctx_for(medium)).status is SignalStatus.WARN

    heavy = [_annual_report(y, ocf=100, capex=80) for y in range(2018, 2023)]
    assert capital_light(_ctx_for(heavy)).status is SignalStatus.FAIL


def test_stable_roe_thresholds() -> None:
    very_stable = [_annual_report(y, roe=0.20) for y in range(2018, 2024)]
    assert stable_roe(_ctx_for(very_stable)).status is SignalStatus.PASS

    swinging = [
        _annual_report(2018, roe=0.05),
        _annual_report(2019, roe=0.25),
        _annual_report(2020, roe=0.10),
        _annual_report(2021, roe=0.30),
        _annual_report(2022, roe=0.15),
    ]
    sig = stable_roe(_ctx_for(swinging))
    # Stddev across [0.05, 0.25, 0.10, 0.30, 0.15] is ~0.10 — boundary case.
    assert sig.status in (SignalStatus.WARN, SignalStatus.FAIL)


def test_stable_gross_margin_thresholds() -> None:
    pass_reports = [_annual_report(y, gross_margin=0.40) for y in range(2018, 2024)]
    assert stable_gross_margin(_ctx_for(pass_reports)).status is SignalStatus.PASS

    fail_reports = [
        _annual_report(2018, gross_margin=0.20),
        _annual_report(2019, gross_margin=0.40),
        _annual_report(2020, gross_margin=0.20),
        _annual_report(2021, gross_margin=0.40),
    ]
    assert stable_gross_margin(_ctx_for(fail_reports)).status is SignalStatus.FAIL


def test_stable_earnings_growth_with_smooth_compounder() -> None:
    # ~25% YoY compounder ⇒ near-zero growth volatility ⇒ PASS. Earnings
    # growth uses TTM-at-Q4 net profit which requires the full quarterly
    # window per year, so we fan out each annual fixture into 4 quarters.
    reports: list[FinancialReport] = []
    for year, fy_np in [
        (2020, 100.0),
        (2021, 125.0),
        (2022, 156.0),
        (2023, 195.0),
        (2024, 244.0),
    ]:
        reports.extend(_full_year_reports(year, net_profit_full_year=fy_np))

    assert stable_earnings_growth(_ctx_for(reports)).status is SignalStatus.PASS


def test_low_leverage_thresholds() -> None:
    pass_reports = [_annual_report(y, debt_ratio=0.30) for y in range(2018, 2024)]
    assert low_leverage(_ctx_for(pass_reports)).status is SignalStatus.PASS

    warn_reports = [_annual_report(y, debt_ratio=0.60) for y in range(2018, 2024)]
    assert low_leverage(_ctx_for(warn_reports)).status is SignalStatus.WARN

    fail_reports = [_annual_report(y, debt_ratio=0.85) for y in range(2018, 2024)]
    assert low_leverage(_ctx_for(fail_reports)).status is SignalStatus.FAIL


def test_liquidity_current_thresholds() -> None:
    pass_reports = [_annual_report(y, current_ratio=2.0) for y in range(2018, 2024)]
    assert liquidity_current(_ctx_for(pass_reports)).status is SignalStatus.PASS

    warn_reports = [_annual_report(y, current_ratio=1.2) for y in range(2018, 2024)]
    assert liquidity_current(_ctx_for(warn_reports)).status is SignalStatus.WARN

    fail_reports = [_annual_report(y, current_ratio=0.7) for y in range(2018, 2024)]
    assert liquidity_current(_ctx_for(fail_reports)).status is SignalStatus.FAIL

    assert liquidity_current(_ctx_for([])).status is SignalStatus.NOT_EVALUATED


def test_liquidity_quick_thresholds() -> None:
    pass_reports = [_annual_report(y, quick_ratio=1.5) for y in range(2018, 2024)]
    assert liquidity_quick(_ctx_for(pass_reports)).status is SignalStatus.PASS

    warn_reports = [_annual_report(y, quick_ratio=0.7) for y in range(2018, 2024)]
    assert liquidity_quick(_ctx_for(warn_reports)).status is SignalStatus.WARN

    fail_reports = [_annual_report(y, quick_ratio=0.3) for y in range(2018, 2024)]
    assert liquidity_quick(_ctx_for(fail_reports)).status is SignalStatus.FAIL


def test_liquidity_quick_not_evaluated_when_upstream_missing() -> None:
    # Mimics HK: current_ratio populated, quick_ratio left None ⇒ N/A.
    reports = [_annual_report(y, current_ratio=1.4) for y in range(2018, 2024)]
    sig = liquidity_quick(_ctx_for(reports))
    assert sig.status is SignalStatus.NOT_EVALUATED
    assert "速动比率" in sig.detail


def test_default_signal_builders_count_and_names_unique() -> None:
    assert DEFAULT_SIGNAL_BUILDERS is CORE_QUALITY_SIGNAL_BUILDERS
    assert len(DEFAULT_SIGNAL_BUILDERS) == 6
    ctx = _ctx_for([])
    names = [b(ctx).name for b in DEFAULT_SIGNAL_BUILDERS]
    assert names == [
        "long_term_roe",
        "roa_quality",
        "fcf_long_term_positive",
        "earnings_cash_backed",
        "ocf_consistency",
        "low_leverage",
    ]


# ====================================================================== #
# QualityAssessment verdict mapping
# ====================================================================== #


def _signal(name: str, status: SignalStatus) -> QualitySignal:
    return QualitySignal(
        name=name, label=name, status=status,
        value=None, threshold=None, detail="",
    )


def test_assessment_excellent_when_pass_dominates_no_fail() -> None:
    sigs = tuple(
        [_signal(f"p{i}", SignalStatus.PASS) for i in range(9)]
        + [_signal("w", SignalStatus.WARN)]
    )
    a = QualityAssessment(signals=sigs)
    assert a.evaluated_count == 10
    assert a.pass_count == 9
    assert a.verdict is Verdict.EXCELLENT
    assert a.score == 5


def test_assessment_good_when_pass_majority_low_fail() -> None:
    sigs = tuple(
        [_signal(f"p{i}", SignalStatus.PASS) for i in range(7)]
        + [_signal("w", SignalStatus.WARN), _signal("w2", SignalStatus.WARN)]
        + [_signal("f", SignalStatus.FAIL)]
    )
    a = QualityAssessment(signals=sigs)
    # pass_ratio 0.7, fail_ratio 0.1 ⇒ GOOD
    assert a.verdict is Verdict.GOOD
    assert a.score == 4


def test_assessment_danger_when_failures_pile_up() -> None:
    sigs = tuple(
        [_signal(f"f{i}", SignalStatus.FAIL) for i in range(5)]
        + [_signal("w", SignalStatus.WARN)]
        + [_signal("p", SignalStatus.PASS)]
    )
    a = QualityAssessment(signals=sigs)
    # fail_ratio ~0.71 ⇒ DANGER
    assert a.verdict is Verdict.DANGER
    assert a.score == 1


def test_assessment_warning_band() -> None:
    sigs = tuple(
        [_signal(f"p{i}", SignalStatus.PASS) for i in range(3)]
        + [_signal("w1", SignalStatus.WARN), _signal("w2", SignalStatus.WARN)]
        + [_signal("f1", SignalStatus.FAIL), _signal("f2", SignalStatus.FAIL)]
    )
    a = QualityAssessment(signals=sigs)
    # pass_ratio ~0.43, fail_ratio ~0.29 ⇒ WARNING
    assert a.verdict is Verdict.WARNING
    assert a.score == 2


def test_assessment_neutral_when_no_dominant_status() -> None:
    sigs = tuple(
        [_signal(f"p{i}", SignalStatus.PASS) for i in range(3)]
        + [_signal(f"w{i}", SignalStatus.WARN) for i in range(3)]
        + [_signal("f", SignalStatus.FAIL)]
    )
    a = QualityAssessment(signals=sigs)
    # pass_ratio ~0.43, fail_ratio ~0.14 ⇒ NEUTRAL band
    assert a.verdict is Verdict.NEUTRAL
    assert a.score == 3


def test_assessment_excludes_not_evaluated_from_denominator() -> None:
    sigs = tuple(
        [_signal(f"p{i}", SignalStatus.PASS) for i in range(8)]
        + [_signal(f"na{i}", SignalStatus.NOT_EVALUATED) for i in range(3)]
    )
    a = QualityAssessment(signals=sigs)
    assert a.evaluated_count == 8
    assert a.not_evaluated_count == 3
    assert a.verdict is Verdict.EXCELLENT


def test_assessment_neutral_when_nothing_evaluated() -> None:
    sigs = tuple(
        _signal(f"na{i}", SignalStatus.NOT_EVALUATED) for i in range(5)
    )
    a = QualityAssessment(signals=sigs)
    assert a.evaluated_count == 0
    assert a.verdict is Verdict.NEUTRAL
    assert a.score == 3
    assert "数据不足" in a.verdict_reason


def test_verdict_reason_mentions_failing_signals() -> None:
    sigs = (
        _signal("p", SignalStatus.PASS),
        _signal("p2", SignalStatus.PASS),
        QualitySignal(
            name="bad", label="坏指标", status=SignalStatus.FAIL,
            value=0.0, threshold=1.0, detail="",
        ),
    )
    a = QualityAssessment(signals=sigs)
    assert "坏指标" in a.verdict_reason


# ====================================================================== #
# Evaluator end-to-end
# ====================================================================== #


def test_evaluator_assess_returns_quality_assessment() -> None:
    reports = [
        _annual_report(
            y,
            roe=0.20, roa=0.10, gross_margin=0.50, net_margin=0.30,
            debt_ratio=0.30,
            current_ratio=2.5, quick_ratio=1.8, cash_ratio=0.8,
            net_profit=100 + 10 * (y - 2018),
            ocf=120 + 10 * (y - 2018),
            capex=10,
            fcf=110 + 10 * (y - 2018),
        )
        for y in range(2018, 2025)
    ]
    history = FinancialHistory.of(_SYMBOL, reports)

    evaluator = QualityEvaluator()
    assessment = evaluator.assess(
        Profitability.from_history(history),
        CashFlowQuality.from_history(history),
        FinancialHealth.from_history(history),
        Stability.from_history(history),
    )

    assert len(assessment.signals) == 6
    # A textbook printing-press should land at EXCELLENT or GOOD.
    assert assessment.verdict in (Verdict.EXCELLENT, Verdict.GOOD)
    assert assessment.score >= 4


def test_evaluator_evaluate_back_compat_triple() -> None:
    reports = [
        _annual_report(
            y, roe=0.20, roa=0.10, gross_margin=0.50, net_margin=0.30,
            debt_ratio=0.30, net_profit=100, ocf=120, capex=10, fcf=110,
        )
        for y in range(2018, 2024)
    ]
    history = FinancialHistory.of(_SYMBOL, reports)

    verdict, reason, score = QualityEvaluator().evaluate(
        Profitability.from_history(history),
        CashFlowQuality.from_history(history),
        FinancialHealth.from_history(history),
        Stability.from_history(history),
    )
    assert isinstance(verdict, Verdict)
    assert isinstance(reason, str) and reason
    assert 1 <= score <= 5


def test_evaluator_evaluate_without_stability_falls_back_gracefully() -> None:
    # Legacy 3-arg call site: stability defaults to empty, which only
    # downgrades the stability-driven signals to NOT_EVALUATED instead of
    # crashing.
    reports = [
        _annual_report(
            y, roe=0.20, roa=0.10, gross_margin=0.50,
            net_profit=100, ocf=120, capex=10, fcf=110,
            debt_ratio=0.30,
        )
        for y in range(2018, 2024)
    ]
    history = FinancialHistory.of(_SYMBOL, reports)

    verdict, _reason, score = QualityEvaluator().evaluate(
        Profitability.from_history(history),
        CashFlowQuality.from_history(history),
        FinancialHealth.from_history(history),
        # No stability arg -> evaluator synthesises an empty one.
    )
    assert verdict is not None
    assert 1 <= score <= 5
