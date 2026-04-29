"""Tests for PE mean - 1σ implied spot price helper used in the valuation step."""

from __future__ import annotations

from datetime import datetime

from backend.application.analysis.steps.valuation import compute_price_at_pe_minus_one_sigma
from backend.domain.valuation.band import HistoricalBand
from backend.domain.valuation.basis import EarningsBasis
from backend.domain.valuation.multiples import PERatio
from backend.domain.valuation.snapshot import ValuationSnapshot


def _snap(*, price: float | None, pe: float | None) -> ValuationSnapshot:
    pe_ratio = PERatio(value=pe, basis=EarningsBasis.TTM) if pe is not None else None
    return ValuationSnapshot(
        as_of_date=datetime(2025, 1, 1),
        price=price,
        market_cap=None,
        pe_ratio=pe_ratio,
        pb_ratio=None,
        ps_ratio=None,
    )


def _band(mean: float, std: float) -> HistoricalBand:
    return HistoricalBand(
        mean=mean,
        std_dev=std,
        low=mean - std,
        high=mean + std,
        sample_size=10,
    )


def test_price_at_minus_one_sigma_scales_linearly_with_pe() -> None:
    # mean=20, std=5 -> target PE = 15; current PE=30, price=100 -> 50
    assert compute_price_at_pe_minus_one_sigma(
        _snap(price=100.0, pe=30.0), _band(20.0, 5.0)
    ) == 50.0


def test_none_when_current_pe_already_at_or_below_target() -> None:
    assert (
        compute_price_at_pe_minus_one_sigma(_snap(price=100.0, pe=15.0), _band(20.0, 5.0))
        is None
    )
    assert (
        compute_price_at_pe_minus_one_sigma(_snap(price=100.0, pe=14.0), _band(20.0, 5.0))
        is None
    )


def test_none_when_band_or_target_invalid() -> None:
    assert compute_price_at_pe_minus_one_sigma(_snap(price=100.0, pe=30.0), None) is None
    assert (
        compute_price_at_pe_minus_one_sigma(
            _snap(price=100.0, pe=30.0),
            _band(10.0, 15.0),
        )
        is None
    )


def test_none_when_no_price_or_pe() -> None:
    b = _band(20.0, 5.0)
    assert compute_price_at_pe_minus_one_sigma(_snap(price=None, pe=30.0), b) is None
    assert compute_price_at_pe_minus_one_sigma(_snap(price=0.0, pe=30.0), b) is None
    assert compute_price_at_pe_minus_one_sigma(_snap(price=100.0, pe=None), b) is None
    assert compute_price_at_pe_minus_one_sigma(_snap(price=100.0, pe=0.0), b) is None


def test_none_when_std_non_positive() -> None:
    b = HistoricalBand(mean=20.0, std_dev=0.0, low=20.0, high=20.0, sample_size=5)
    assert compute_price_at_pe_minus_one_sigma(_snap(price=100.0, pe=30.0), b) is None
