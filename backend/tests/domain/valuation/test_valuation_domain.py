from __future__ import annotations

import logging
from datetime import date, datetime

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
from backend.domain.quality.profitability import ReturnOnEquity
from backend.domain.stocks.market import Market
from backend.domain.stocks.snapshot import StockSnapshot
from backend.domain.stocks.symbol import Symbol
from backend.domain.valuation.assessment import ValuationAssessment
from backend.domain.valuation.band import HistoricalBand, Percentile
from backend.domain.valuation.basis import EarningsBasis
from backend.domain.valuation.comparable import ComparablePeer, ComparableSet
from backend.domain.valuation.evaluator import ValuationEvaluator
from backend.domain.valuation.history import (
    ValuationHistory,
    dividend_yield_metric,
    pb_metric,
    pe_metric,
    ps_metric,
    ttm_profit_timeline_from_history,
)
from backend.domain.valuation.multiples import (
    PBRatio,
    PEGRatio,
    PERatio,
    PSRatio,
    ValuationMultiple,
)
from backend.domain.valuation.snapshot import ValuationSnapshot
from backend.domain.verdict import Verdict


# --------------------------------------------------------------------------- #
# Test fixtures / builders
# --------------------------------------------------------------------------- #


_SYMBOL = Symbol(code="600519", market=Market.A)


def _period(year: int, quarter: int) -> ReportPeriod:
    month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    month, day = month_day[quarter]
    return ReportPeriod.quarterly(year, quarter, date(year, month, day))


def _report(
    year: int,
    quarter: int,
    *,
    revenue: float,
    net_profit_deducted: float,
    roe: float | None = None,
) -> FinancialReport:
    return FinancialReport(
        security_id=_SYMBOL,
        period=_period(year, quarter),
        accounting=AccountingContext(
            currency="CNY",
            standard=ReportingStandard.CAS,
            period_presentation=PeriodPresentation.YTD_CUMULATIVE,
        ),
        income_statement=IncomeStatement(
            revenue=revenue,
            net_profit=net_profit_deducted,
            net_profit_deducted=net_profit_deducted,
        ),
        balance_sheet=BalanceSheet(
            total_assets=1000.0, total_liabilities=400.0, total_equity=600.0
        ),
        cash_flow_statement=CashFlowStatement(),
        metrics=FinancialMetrics(roe=roe) if roe is not None else FinancialMetrics(),
    )


def _full_year_history() -> FinancialHistory:
    """4-quarter YTD history yielding TTM revenue=11.5e9, TTM profit=1.25e9 at Q4."""
    return FinancialHistory.of(
        _SYMBOL,
        [
            _report(2024, 1, revenue=2.5e9, net_profit_deducted=2.5e8, roe=0.03),
            _report(2024, 2, revenue=5.5e9, net_profit_deducted=5.5e8, roe=0.07),
            _report(2024, 3, revenue=8.5e9, net_profit_deducted=8.5e8, roe=0.11),
            _report(2024, 4, revenue=1.15e10, net_profit_deducted=1.25e9, roe=0.15),
        ],
    )


def _stock_snapshot(
    *,
    current_price: float | None = 150.0,
    market_cap: float | None = 1.5e10,
    total_shares: float | None = 1.0e8,
) -> StockSnapshot:
    return StockSnapshot(
        symbol=_SYMBOL,
        current_price=current_price,
        market_cap=market_cap,
        total_shares=total_shares,
        as_of=datetime(2025, 1, 5, 9, 30),
    )


def _pe_only_snapshot(period: str, pe: float) -> ValuationSnapshot:
    """Build a thin historical snapshot carrying just a PE point."""
    return ValuationSnapshot(
        as_of_date=datetime.strptime(period, "%Y-%m"),
        price=None,
        market_cap=None,
        pe_ratio=PERatio(value=pe, basis=EarningsBasis.TTM),
        pb_ratio=None,
        ps_ratio=None,
    )


# --------------------------------------------------------------------------- #
# EarningsBasis
# --------------------------------------------------------------------------- #


def test_earnings_basis_string_values() -> None:
    assert EarningsBasis.TTM.value == "ttm"
    assert EarningsBasis.FORWARD.value == "forward"
    assert EarningsBasis.NORMALIZED.value == "normalized"


# --------------------------------------------------------------------------- #
# ValuationMultiple protocol
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "multiple",
    [
        PERatio(value=12.0),
        PBRatio(value=2.0),
        PSRatio(value=1.5),
        PEGRatio(value=0.8),
    ],
)
def test_all_multiples_satisfy_valuation_multiple_protocol(
    multiple: ValuationMultiple,
) -> None:
    assert isinstance(multiple, ValuationMultiple)
    assert isinstance(multiple.value, float)


# --------------------------------------------------------------------------- #
# PERatio
# --------------------------------------------------------------------------- #


def test_pe_ratio_default_basis_is_ttm() -> None:
    assert PERatio(value=10.0).basis is EarningsBasis.TTM


def test_pe_ratio_from_market_cap_returns_none_for_unusable_inputs() -> None:
    assert PERatio.from_market_cap(None, 100.0) is None
    assert PERatio.from_market_cap(0.0, 100.0) is None
    assert PERatio.from_market_cap(1000.0, None) is None
    assert PERatio.from_market_cap(1000.0, 0.0) is None
    assert PERatio.from_market_cap(1000.0, -50.0) is None


def test_pe_ratio_from_market_cap_propagates_basis() -> None:
    pe = PERatio.from_market_cap(1200.0, 100.0, basis=EarningsBasis.FORWARD)
    assert pe is not None
    assert pe.value == 12.0
    assert pe.basis is EarningsBasis.FORWARD


def test_pe_ratio_compute_pb_returns_none_when_roe_unusable() -> None:
    pe = PERatio(value=12.0)
    history = FinancialHistory.of(_SYMBOL, [])
    assert pe.compute_pb(ReturnOnEquity.from_history(history)) is None


def test_pe_ratio_compute_pb_multiplies_latest_roe() -> None:
    history = _full_year_history()
    roe = ReturnOnEquity.from_history(history)
    pb = PERatio(value=12.0).compute_pb(roe)
    assert pb is not None
    assert pb.value == pytest.approx(12.0 * 0.15)


# --------------------------------------------------------------------------- #
# PBRatio
# --------------------------------------------------------------------------- #


def test_pb_ratio_from_market_cap_returns_none_for_unusable_inputs() -> None:
    assert PBRatio.from_market_cap(None, 1000.0) is None
    assert PBRatio.from_market_cap(2000.0, None) is None
    assert PBRatio.from_market_cap(2000.0, 0.0) is None
    assert PBRatio.from_market_cap(2000.0, -100.0) is None


def test_pb_ratio_from_market_cap_returns_value() -> None:
    pb = PBRatio.from_market_cap(2000.0, 1000.0)
    assert pb is not None
    assert pb.value == 2.0


# --------------------------------------------------------------------------- #
# PSRatio
# --------------------------------------------------------------------------- #


def test_ps_ratio_default_basis_is_ttm() -> None:
    assert PSRatio(value=2.0).basis is EarningsBasis.TTM


def test_ps_ratio_from_market_cap_returns_none_for_unusable_inputs() -> None:
    assert PSRatio.from_market_cap(None, 1000.0) is None
    assert PSRatio.from_market_cap(2000.0, None) is None
    assert PSRatio.from_market_cap(2000.0, 0.0) is None
    assert PSRatio.from_market_cap(2000.0, -1.0) is None


def test_ps_ratio_from_market_cap_propagates_basis() -> None:
    ps = PSRatio.from_market_cap(2000.0, 1000.0, basis=EarningsBasis.FORWARD)
    assert ps is not None
    assert ps.value == 2.0
    assert ps.basis is EarningsBasis.FORWARD


# --------------------------------------------------------------------------- #
# PEGRatio
# --------------------------------------------------------------------------- #


def test_peg_ratio_from_pe_returns_none_for_unusable_inputs() -> None:
    pe = PERatio(value=12.0, basis=EarningsBasis.TTM)
    assert PEGRatio.from_pe(None, 0.1) is None
    assert PEGRatio.from_pe(pe, None) is None
    assert PEGRatio.from_pe(pe, 0.0) is None
    assert PEGRatio.from_pe(pe, -0.05) is None


def test_peg_ratio_inherits_basis_from_underlying_pe() -> None:
    pe_fwd = PERatio(value=20.0, basis=EarningsBasis.FORWARD)
    peg = PEGRatio.from_pe(pe_fwd, 0.20)
    assert peg is not None
    # PEG = PE / (growth * 100) = 20 / 20 = 1.0
    assert peg.value == pytest.approx(1.0)
    assert peg.basis is EarningsBasis.FORWARD


# --------------------------------------------------------------------------- #
# HistoricalBand
# --------------------------------------------------------------------------- #


def test_historical_band_returns_none_for_small_samples() -> None:
    assert HistoricalBand.from_values([]) is None
    assert HistoricalBand.from_values([10.0]) is None
    assert HistoricalBand.from_values([10.0, 12.0]) is None


def test_historical_band_computes_mean_std_and_low_clipped_to_min() -> None:
    band = HistoricalBand.from_values([10.0, 12.0, 14.0])
    assert band is not None
    assert band.sample_size == 3
    assert band.mean == pytest.approx(12.0)
    # Low must never dip below the observed minimum.
    assert band.low >= 10.0


# --------------------------------------------------------------------------- #
# Percentile
# --------------------------------------------------------------------------- #


def test_percentile_returns_none_when_inputs_unusable() -> None:
    assert Percentile.of([], current=10.0) is None
    assert Percentile.of([1.0, 2.0, 3.0], current=None) is None


def test_percentile_counts_values_at_or_below_current() -> None:
    pct = Percentile.of([10.0, 20.0, 30.0, 40.0], current=20.0)
    assert pct is not None
    assert pct.value == pytest.approx(0.5)
    assert pct.sample_size == 4

    top = Percentile.of([10.0, 20.0, 30.0, 40.0], current=40.0)
    assert top is not None and top.value == 1.0

    below = Percentile.of([10.0, 20.0, 30.0, 40.0], current=5.0)
    assert below is not None and below.value == 0.0


# --------------------------------------------------------------------------- #
# ValuationSnapshot
# --------------------------------------------------------------------------- #


def test_valuation_snapshot_value_accessors_unwrap_or_return_none() -> None:
    s = ValuationSnapshot(
        as_of_date=datetime(2025, 1, 1),
        price=10.0,
        market_cap=1.0e10,
        pe_ratio=PERatio(value=15.0),
        pb_ratio=PBRatio(value=2.0),
        ps_ratio=PSRatio(value=3.0),
        ev_ebit=None,
        dividend_yield=0.025,
    )
    assert s.pe_value == 15.0
    assert s.pb_value == 2.0
    assert s.ps_value == 3.0
    assert s.dividend_yield == 0.025
    assert s.ev_ebit is None

    empty = ValuationSnapshot(
        as_of_date=datetime(2025, 1, 1),
        price=None,
        market_cap=None,
        pe_ratio=None,
        pb_ratio=None,
        ps_ratio=None,
    )
    assert empty.pe_value is None
    assert empty.pb_value is None
    assert empty.ps_value is None


def test_valuation_snapshot_from_inputs_composes_pe_pb_ps() -> None:
    history = _full_year_history()
    roe = ReturnOnEquity.from_history(history)
    snapshot = ValuationSnapshot.from_inputs(
        _stock_snapshot(), history, roe, dividend_yield=0.018
    )
    # PE = market_cap / TTM net_profit_deducted = 1.5e10 / 1.25e9
    assert snapshot.pe_ratio is not None
    assert snapshot.pe_ratio.value == pytest.approx(12.0)
    assert snapshot.pe_ratio.basis is EarningsBasis.TTM
    # PB = PE * latest_roe = 12 * 0.15
    assert snapshot.pb_ratio is not None
    assert snapshot.pb_ratio.value == pytest.approx(1.80)
    # PS = market_cap / TTM revenue = 1.5e10 / 1.15e10
    assert snapshot.ps_ratio is not None
    assert snapshot.ps_ratio.value == pytest.approx(1.5e10 / 1.15e10)
    assert snapshot.dividend_yield == 0.018
    assert snapshot.ev_ebit is None
    assert snapshot.price == 150.0
    assert snapshot.market_cap == 1.5e10


def test_valuation_snapshot_from_inputs_derives_price_from_market_cap() -> None:
    """When the quote feed omits ``current_price`` we fall back to mcap/shares."""
    history = _full_year_history()
    roe = ReturnOnEquity.from_history(history)
    stock = _stock_snapshot(current_price=None, market_cap=1.5e10, total_shares=1.0e8)
    snapshot = ValuationSnapshot.from_inputs(stock, history, roe)
    assert snapshot.price == 150.0


def test_valuation_snapshot_from_inputs_returns_none_multiples_without_ttm() -> None:
    """A single quarterly report cannot yield TTM, so multiples must be None."""
    history = FinancialHistory.of(
        _SYMBOL,
        [_report(2024, 1, revenue=2.5e9, net_profit_deducted=2.5e8, roe=0.03)],
    )
    roe = ReturnOnEquity.from_history(history)
    snapshot = ValuationSnapshot.from_inputs(_stock_snapshot(), history, roe)
    assert snapshot.pe_ratio is None
    assert snapshot.pb_ratio is None
    assert snapshot.ps_ratio is None


# --------------------------------------------------------------------------- #
# ValuationHistory + ttm_profit_timeline_from_history
# --------------------------------------------------------------------------- #


def test_ttm_profit_timeline_yields_one_pair_per_complete_quarter() -> None:
    history = _full_year_history()
    timeline = ttm_profit_timeline_from_history(history)
    # YTD-cumulative with 4 quarters: TTM is only well-defined at Q4.
    assert timeline == [("2024-12", 1.25e9)]


def test_valuation_history_from_inputs_aligns_market_cap_to_ttm_timeline() -> None:
    # Both market_cap_monthly and ttm_profit_timeline are in raw yuan.
    history = ValuationHistory.from_inputs(
        market_cap_monthly=[
            ("2024-01", 100e8),
            ("2024-02", 110e8),
            ("2024-03", 105e8),
        ],
        ttm_profit_timeline=[("2023-12", 5.0e8)],
    )
    pairs = history.metric_pairs()
    # 100亿 / 5亿 = 20, 110亿 / 5亿 = 22, 105亿 / 5亿 = 21
    assert pairs == [("2024-01", 20.0), ("2024-02", 22.0), ("2024-03", 21.0)]


def test_valuation_history_from_inputs_drops_pathological_pe_points() -> None:
    """PE ≥ 500 (overheated) and PE ≤ 0 (negative profit) must be dropped."""
    history = ValuationHistory.from_inputs(
        market_cap_monthly=[
            ("2024-01", 100e8),  # PE = 100亿/0.1亿 = 1000 → dropped
            ("2024-02", 100e8),  # PE = 100亿/-1 → ttm_profit ≤ 0 → dropped
            ("2024-03", 100e8),  # PE = 100亿/5亿 = 20 → kept
        ],
        ttm_profit_timeline=[
            ("2024-01", 1.0e7),
            ("2024-02", -1.0),
            ("2024-03", 5.0e8),
        ],
    )
    assert history.metric_pairs() == [("2024-03", 20.0)]


def test_valuation_history_from_inputs_skips_periods_before_first_ttm_point() -> None:
    history = ValuationHistory.from_inputs(
        market_cap_monthly=[("2023-01", 100e8), ("2024-03", 100e8)],
        ttm_profit_timeline=[("2024-01", 5.0e8)],
    )
    assert [p for p, _ in history.metric_pairs()] == ["2024-03"]


def test_valuation_history_from_inputs_returns_empty_when_either_input_missing() -> None:
    assert ValuationHistory.from_inputs([], [("2024-01", 1.0e9)]).is_empty()
    assert ValuationHistory.from_inputs([("2024-01", 100e8)], []).is_empty()


def test_valuation_history_with_seed_carries_a_single_pe_snapshot() -> None:
    seeded = ValuationHistory(snapshots=()).with_seed("2024-01", pe=18.567)
    assert len(seeded.snapshots) == 1
    snap = seeded.snapshots[0]
    assert snap.as_of_date == datetime(2024, 1, 1)
    assert snap.pe_ratio is not None
    assert snap.pe_ratio.value == 18.57  # rounded to 2 decimals
    assert snap.pb_ratio is None
    assert snap.ps_ratio is None


def test_valuation_history_metric_projections_select_per_metric() -> None:
    """Per-metric projection skips snapshots where the metric is missing."""
    snapshots = (
        ValuationSnapshot(
            as_of_date=datetime(2024, 1, 1),
            price=None,
            market_cap=None,
            pe_ratio=PERatio(value=15.0),
            pb_ratio=PBRatio(value=2.0),
            ps_ratio=None,
            dividend_yield=0.03,
        ),
        ValuationSnapshot(
            as_of_date=datetime(2024, 2, 1),
            price=None,
            market_cap=None,
            pe_ratio=PERatio(value=18.0),
            pb_ratio=None,
            ps_ratio=PSRatio(value=1.5),
            dividend_yield=None,
        ),
    )
    h = ValuationHistory(snapshots=snapshots)

    # Default projection is PE.
    assert h.metric_values() == [15.0, 18.0]
    # PB skips the second snapshot, PS skips the first; dividend_yield same.
    assert h.metric_values(pb_metric) == [2.0]
    assert h.metric_values(ps_metric) == [1.5]
    assert h.metric_values(dividend_yield_metric) == [0.03]
    # metric_pairs labels each snapshot's as_of_date as YYYY-MM.
    assert h.metric_pairs(pe_metric) == [("2024-01", 15.0), ("2024-02", 18.0)]


def test_valuation_history_band_and_percentile_use_chosen_projection() -> None:
    """Band and percentile must operate on the projected metric, not raw PE."""
    snapshots = tuple(
        ValuationSnapshot(
            as_of_date=datetime(2024, m, 1),
            price=None,
            market_cap=None,
            pe_ratio=PERatio(value=10.0 + m),
            pb_ratio=PBRatio(value=1.0 + 0.1 * m),
            ps_ratio=None,
        )
        for m in range(1, 6)
    )
    h = ValuationHistory(snapshots=snapshots)

    pe_band = h.band()
    pb_band = h.band(pb_metric)
    assert pe_band is not None and pb_band is not None
    assert pe_band.mean == pytest.approx(13.0)
    assert pb_band.mean == pytest.approx(1.3)

    pe_pct = h.percentile_of(13.0)
    pb_pct = h.percentile_of(1.3, pb_metric)
    assert pe_pct is not None and pe_pct.value == pytest.approx(0.6)
    assert pb_pct is not None and pb_pct.value == pytest.approx(0.6)


# --------------------------------------------------------------------------- #
# ValuationAssessment
# --------------------------------------------------------------------------- #


def test_valuation_assessment_carries_optional_signals() -> None:
    a = ValuationAssessment(
        verdict=Verdict.GOOD,
        reason="ok",
        score=4,
        z_score=-1.2,
        percentile=0.18,
    )
    assert a.verdict is Verdict.GOOD
    assert a.score == 4
    assert a.z_score == -1.2
    assert a.percentile == 0.18

    minimal = ValuationAssessment(verdict=Verdict.NEUTRAL, reason="...", score=3)
    assert minimal.z_score is None
    assert minimal.percentile is None


# --------------------------------------------------------------------------- #
# ValuationEvaluator
# --------------------------------------------------------------------------- #


def _history_around(mean_pe: float, *, jitter: float = 1.0) -> ValuationHistory:
    """Build a history whose PE distribution has ``mean ≈ mean_pe`` and σ > 0."""
    points = [mean_pe - jitter, mean_pe, mean_pe + jitter] * 3
    snapshots = tuple(
        _pe_only_snapshot(f"2024-{i + 1:02d}", pe) for i, pe in enumerate(points)
    )
    return ValuationHistory(snapshots=snapshots)


def _snapshot_with_pe(pe_value: float) -> ValuationSnapshot:
    return ValuationSnapshot(
        as_of_date=datetime(2025, 1, 1),
        price=None,
        market_cap=None,
        pe_ratio=PERatio(value=pe_value),
        pb_ratio=None,
        ps_ratio=None,
    )


def test_evaluator_z_score_excellent_when_low_pe_and_low_peg() -> None:
    history = _history_around(20.0, jitter=2.0)
    snapshot = _snapshot_with_pe(15.0)  # ≈ -1.96σ
    peg = PEGRatio(value=0.5)
    a = ValuationEvaluator().evaluate(snapshot, history, peg=peg)
    assert a.verdict is Verdict.EXCELLENT
    assert a.score == 5
    assert a.z_score is not None and a.z_score < -1.0


def test_evaluator_z_score_good_when_low_pe_without_qualifying_peg() -> None:
    history = _history_around(20.0, jitter=2.0)
    snapshot = _snapshot_with_pe(15.0)
    a = ValuationEvaluator().evaluate(snapshot, history)
    assert a.verdict is Verdict.GOOD
    assert a.score == 4


def test_evaluator_z_score_neutral_within_one_sigma() -> None:
    history = _history_around(20.0, jitter=2.0)
    snapshot = _snapshot_with_pe(20.5)
    a = ValuationEvaluator().evaluate(snapshot, history)
    assert a.verdict is Verdict.NEUTRAL
    assert a.score == 3


def test_evaluator_z_score_warning_above_one_sigma() -> None:
    history = _history_around(20.0, jitter=2.0)
    snapshot = _snapshot_with_pe(22.5)
    a = ValuationEvaluator().evaluate(snapshot, history)
    assert a.verdict is Verdict.WARNING
    assert a.score == 2


def test_evaluator_z_score_danger_at_or_above_two_sigma() -> None:
    history = _history_around(20.0, jitter=2.0)
    snapshot = _snapshot_with_pe(25.0)  # ≈ +3σ
    a = ValuationEvaluator().evaluate(snapshot, history)
    assert a.verdict is Verdict.DANGER
    assert a.score == 1


def test_evaluator_falls_back_to_percentile_when_band_unavailable() -> None:
    """Fewer than 3 PE points → band is None → percentile branch fires.

    The signal carried on the assessment must reflect that fallback: ``z_score``
    stays ``None`` while ``percentile`` is populated.
    """
    history = ValuationHistory(
        snapshots=(
            _pe_only_snapshot("2024-01", 10.0),
            _pe_only_snapshot("2024-02", 30.0),
        ),
    )
    a = ValuationEvaluator().evaluate(_snapshot_with_pe(20.0), history)
    assert a.z_score is None
    assert a.percentile == pytest.approx(0.5)
    assert a.verdict is Verdict.NEUTRAL


def test_evaluator_percentile_branch_thresholds() -> None:
    """≤ 0.30 → GOOD, ≥ 0.80 → DANGER, otherwise NEUTRAL."""
    # Two equal points so percentile is fully discrete (0.0 / 0.5 / 1.0).
    history = ValuationHistory(
        snapshots=(
            _pe_only_snapshot("2024-01", 20.0),
            _pe_only_snapshot("2024-02", 20.0),
        ),
    )
    cheap = ValuationEvaluator().evaluate(_snapshot_with_pe(10.0), history)
    assert cheap.verdict is Verdict.GOOD  # percentile = 0.0
    expensive = ValuationEvaluator().evaluate(_snapshot_with_pe(30.0), history)
    assert expensive.verdict is Verdict.DANGER  # percentile = 1.0
    middling = ValuationEvaluator().evaluate(
        _snapshot_with_pe(20.0),
        ValuationHistory(
            snapshots=(
                _pe_only_snapshot("2024-01", 10.0),
                _pe_only_snapshot("2024-02", 30.0),
            ),
        ),
    )
    assert middling.verdict is Verdict.NEUTRAL  # percentile = 0.5


def test_evaluator_absolute_thresholds_when_no_history_signal() -> None:
    """Empty history → falls through to absolute PE thresholds."""
    empty = ValuationHistory(snapshots=())

    cheap = ValuationEvaluator().evaluate(_snapshot_with_pe(10.0), empty)
    assert cheap.verdict is Verdict.GOOD and cheap.score == 4

    expensive = ValuationEvaluator().evaluate(_snapshot_with_pe(60.0), empty)
    assert expensive.verdict is Verdict.WARNING and expensive.score == 2

    middling = ValuationEvaluator().evaluate(_snapshot_with_pe(25.0), empty)
    assert middling.verdict is Verdict.NEUTRAL and middling.score == 3


def test_evaluator_returns_neutral_when_pe_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    empty = ValuationHistory(snapshots=())
    snap = ValuationSnapshot(
        as_of_date=datetime(2025, 1, 1),
        price=None,
        market_cap=None,
        pe_ratio=None,
        pb_ratio=None,
        ps_ratio=None,
    )
    with caplog.at_level(logging.WARNING, logger="backend.domain.valuation.evaluator"):
        a = ValuationEvaluator().evaluate(snap, empty)
    assert a.verdict is Verdict.NEUTRAL
    assert a.score == 3
    assert "无法获取估值数据" in a.reason
    # The no-data path must surface a warning so operators can investigate.
    assert any(
        "no usable valuation data" in record.message
        and record.levelno == logging.WARNING
        for record in caplog.records
    )


def test_evaluator_does_not_warn_on_happy_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    history = _history_around(20.0, jitter=2.0)
    snapshot = _snapshot_with_pe(20.5)
    with caplog.at_level(logging.WARNING, logger="backend.domain.valuation.evaluator"):
        ValuationEvaluator().evaluate(snapshot, history)
    assert caplog.records == []


# --------------------------------------------------------------------------- #
# ComparableSet / ComparablePeer
# --------------------------------------------------------------------------- #


def _peer(code: str, *, pe: float, pb: float | None = None) -> ComparablePeer:
    return ComparablePeer(
        security_id=Symbol(code=code, market=Market.A),
        snapshot=ValuationSnapshot(
            as_of_date=datetime(2025, 1, 1),
            price=None,
            market_cap=None,
            pe_ratio=PERatio(value=pe),
            pb_ratio=PBRatio(value=pb) if pb is not None else None,
            ps_ratio=None,
        ),
    )


def test_comparable_set_of_and_is_empty() -> None:
    assert ComparableSet.of([]).is_empty() is True
    assert ComparableSet.of([_peer("600519", pe=12.0)]).is_empty() is False


def test_comparable_set_values_and_average_default_to_pe_metric() -> None:
    peers = [_peer("600519", pe=10.0), _peer("000333", pe=20.0), _peer("002230", pe=30.0)]
    cs = ComparableSet.of(peers)
    assert cs.values() == [10.0, 20.0, 30.0]
    assert cs.average() == pytest.approx(20.0)


def test_comparable_set_median_handles_odd_and_even_lengths() -> None:
    odd = ComparableSet.of(
        [_peer("a", pe=10.0), _peer("b", pe=30.0), _peer("c", pe=20.0)]
    )
    assert odd.median() == 20.0

    even = ComparableSet.of(
        [_peer("a", pe=10.0), _peer("b", pe=20.0), _peer("c", pe=30.0), _peer("d", pe=40.0)]
    )
    assert even.median() == 25.0

    assert ComparableSet.of([]).median() is None
    assert ComparableSet.of([]).average() is None


def test_comparable_set_projects_to_alternate_metric() -> None:
    peers = [
        _peer("a", pe=10.0, pb=1.0),
        _peer("b", pe=20.0, pb=None),  # PB missing → projection skips
        _peer("c", pe=30.0, pb=3.0),
    ]
    cs = ComparableSet.of(peers)
    assert cs.values(pb_metric) == [1.0, 3.0]
    assert cs.median(pb_metric) == pytest.approx(2.0)
    assert cs.average(pb_metric) == pytest.approx(2.0)
