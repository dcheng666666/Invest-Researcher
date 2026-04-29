from __future__ import annotations

from datetime import date, datetime

import pytest

from backend.domain.dividends.aggregation import aggregate_history
from backend.domain.dividends.amounts import (
    DividendPerShare,
    DividendYield,
    PayoutRatio,
)
from backend.domain.dividends.history import DividendHistory
from backend.domain.dividends.ratios import compute_dividend_ratios
from backend.domain.dividends.record import DividendRecord
from backend.domain.dividends.track_record import DividendTrackRecord
from backend.domain.dividends.types import DividendType


# --------------------------------------------------------------------------- #
# DividendType
# --------------------------------------------------------------------------- #


def test_dividend_type_is_cash_only_for_cash_and_special() -> None:
    assert DividendType.CASH.is_cash is True
    assert DividendType.SPECIAL.is_cash is True
    assert DividendType.STOCK.is_cash is False
    assert DividendType.SCRIP.is_cash is False
    assert DividendType.OTHER.is_cash is False


# --------------------------------------------------------------------------- #
# DividendPerShare
# --------------------------------------------------------------------------- #


def test_dividend_per_share_rejects_negative_amount_and_blank_currency() -> None:
    with pytest.raises(ValueError):
        DividendPerShare(amount=-0.01, currency="CNY")
    with pytest.raises(ValueError):
        DividendPerShare(amount=0.1, currency="")


def test_dividend_per_share_zero_factory_and_is_zero_property() -> None:
    z = DividendPerShare.zero("HKD")
    assert z.amount == 0.0
    assert z.currency == "HKD"
    assert z.is_zero is True
    assert DividendPerShare(0.01, "HKD").is_zero is False


def test_dividend_per_share_addition_preserves_currency_and_sums_amount() -> None:
    summed = DividendPerShare(0.1, "CNY") + DividendPerShare(0.2, "CNY")
    assert summed.currency == "CNY"
    assert summed.amount == pytest.approx(0.3)


def test_dividend_per_share_addition_rejects_mixed_currency() -> None:
    with pytest.raises(ValueError):
        DividendPerShare(0.1, "CNY") + DividendPerShare(0.1, "HKD")


# --------------------------------------------------------------------------- #
# PayoutRatio
# --------------------------------------------------------------------------- #


def test_payout_ratio_rejects_negative_value() -> None:
    assert PayoutRatio(0.0).value == 0.0
    with pytest.raises(ValueError):
        PayoutRatio(-0.01)


def test_payout_ratio_of_returns_none_for_unusable_denominator() -> None:
    assert PayoutRatio.of(dividend_total=100.0, net_profit=0.0) is None
    assert PayoutRatio.of(dividend_total=100.0, net_profit=-10.0) is None


def test_payout_ratio_of_rounds_to_four_decimals() -> None:
    ratio = PayoutRatio.of(dividend_total=33.33333, net_profit=100.0)
    assert ratio is not None
    assert ratio.value == 0.3333


def test_payout_ratio_of_caps_at_two() -> None:
    ratio = PayoutRatio.of(dividend_total=500.0, net_profit=100.0)
    assert ratio is not None
    assert ratio.value == 2.0


def test_payout_ratio_from_dps_eps_rejects_unusable_eps() -> None:
    assert PayoutRatio.from_dps_eps(0.5, None) is None
    assert PayoutRatio.from_dps_eps(0.5, 0.0) is None
    assert PayoutRatio.from_dps_eps(0.5, -0.1) is None


def test_payout_ratio_from_dps_eps_divides_dps_by_eps_and_caps_at_two() -> None:
    payout = PayoutRatio.from_dps_eps(0.4, 1.0)
    assert payout is not None
    assert payout.value == 0.4

    capped = PayoutRatio.from_dps_eps(5.0, 1.0)
    assert capped is not None
    assert capped.value == 2.0


# --------------------------------------------------------------------------- #
# DividendYield
# --------------------------------------------------------------------------- #


def test_dividend_yield_rejects_negative_value() -> None:
    assert DividendYield(0.0).value == 0.0
    with pytest.raises(ValueError):
        DividendYield(-0.01)


def test_dividend_yield_of_returns_none_for_non_positive_price() -> None:
    dps = DividendPerShare(0.5, "CNY")
    assert DividendYield.of(dps, current_price=0.0) is None
    assert DividendYield.of(dps, current_price=-1.0) is None


def test_dividend_yield_of_divides_dps_by_price() -> None:
    dy = DividendYield.of(DividendPerShare(0.5, "CNY"), current_price=25.0)
    assert dy is not None
    assert dy.value == 0.02


# --------------------------------------------------------------------------- #
# DividendRecord
# --------------------------------------------------------------------------- #


def _record(
    fiscal_year: str = "2023",
    *,
    amount: float = 0.1,
    currency: str = "CNY",
    dividend_type: DividendType = DividendType.CASH,
    announcement_date: date | None = None,
    ex_dividend_date: date | None = None,
    payment_date: date | None = None,
) -> DividendRecord:
    return DividendRecord(
        fiscal_year=fiscal_year,
        dividend_per_share=DividendPerShare(amount, currency),
        dividend_type=dividend_type,
        announcement_date=announcement_date,
        ex_dividend_date=ex_dividend_date,
        payment_date=payment_date,
    )


def test_dividend_record_requires_non_empty_fiscal_year() -> None:
    with pytest.raises(ValueError):
        DividendRecord(
            fiscal_year="",
            dividend_per_share=DividendPerShare(0.1, "CNY"),
        )


def test_dividend_record_helpers_reflect_type_and_currency() -> None:
    cash = _record(dividend_type=DividendType.CASH)
    stock = _record(amount=0.0, dividend_type=DividendType.STOCK)
    assert cash.is_cash is True
    assert cash.currency == "CNY"
    assert stock.is_cash is False
    assert stock.currency == "CNY"


# --------------------------------------------------------------------------- #
# DividendHistory
# --------------------------------------------------------------------------- #


def test_dividend_history_empty_factory_has_no_records_and_unknown_currency() -> None:
    h = DividendHistory.empty()
    assert h.is_empty is True
    assert h.records == ()
    assert h.currency is None
    assert h.has_no_distribution is False


def test_dividend_history_empty_factory_preserves_no_distribution_flag() -> None:
    h = DividendHistory.empty(has_no_distribution=True)
    assert h.is_empty is True
    assert h.has_no_distribution is True


def test_dividend_history_of_factory_keeps_records_and_currency() -> None:
    rec = _record(fiscal_year="2023")
    h = DividendHistory.of([rec])
    assert h.is_empty is False
    assert h.records == (rec,)
    assert h.currency == "CNY"


def test_dividend_history_rejects_records_with_mixed_currencies() -> None:
    cny = _record(currency="CNY")
    hkd = _record(currency="HKD")
    with pytest.raises(ValueError):
        DividendHistory.of([cny, hkd])


def test_dividend_history_cash_records_filters_non_cash_distributions() -> None:
    cash = _record(dividend_type=DividendType.CASH)
    special = _record(amount=0.05, dividend_type=DividendType.SPECIAL)
    stock = _record(amount=0.0, dividend_type=DividendType.STOCK)
    scrip = _record(amount=0.0, dividend_type=DividendType.SCRIP)
    h = DividendHistory.of([cash, special, stock, scrip])
    assert h.cash_records() == (cash, special)


# --------------------------------------------------------------------------- #
# DividendTrackRecord
# --------------------------------------------------------------------------- #


def test_dividend_track_record_empty_helpers() -> None:
    empty = DividendTrackRecord.empty()
    assert empty.is_empty is True
    assert empty.years() == []
    assert empty.get("2023") is None


def test_dividend_track_record_lookup_helpers() -> None:
    tr = DividendTrackRecord(
        annual_dps=(
            ("2022", DividendPerShare(0.5, "CNY")),
            ("2023", DividendPerShare(0.7, "CNY")),
        ),
        annual_distribution_counts=(("2022", 1), ("2023", 2)),
    )
    assert tr.is_empty is False
    assert tr.years() == ["2022", "2023"]
    fy23 = tr.get("2023")
    assert fy23 is not None
    assert fy23.amount == 0.7
    assert fy23.currency == "CNY"
    assert tr.get("2024") is None


# --------------------------------------------------------------------------- #
# aggregate_history
# --------------------------------------------------------------------------- #


def test_aggregate_history_returns_empty_for_empty_history() -> None:
    h = DividendHistory.empty(has_no_distribution=True)
    assert aggregate_history(h).is_empty is True


def test_aggregate_history_buckets_by_fiscal_year_and_sums_within_year() -> None:
    history = DividendHistory.of(
        [
            _record(fiscal_year="2020", amount=0.2),
            _record(fiscal_year="2021", amount=0.3),
            _record(fiscal_year="2021", amount=0.4),
        ],
    )
    track = aggregate_history(history)

    assert track.years() == ["2020", "2021"]
    fy20 = track.get("2020")
    fy21 = track.get("2021")
    assert fy20 is not None and fy20.amount == pytest.approx(0.2)
    assert fy21 is not None and fy21.amount == pytest.approx(0.7)
    assert dict(track.annual_distribution_counts) == {"2020": 1, "2021": 2}


def test_aggregate_history_skips_non_cash_and_zero_amount_records() -> None:
    history = DividendHistory.of(
        [
            _record(fiscal_year="2023", amount=0.5, dividend_type=DividendType.CASH),
            _record(fiscal_year="2023", amount=0.5, dividend_type=DividendType.STOCK),
            _record(fiscal_year="2023", amount=0.0, dividend_type=DividendType.CASH),
        ],
    )
    track = aggregate_history(history)

    assert track.years() == ["2023"]
    fy23 = track.get("2023")
    assert fy23 is not None
    assert fy23.amount == pytest.approx(0.5)
    assert dict(track.annual_distribution_counts) == {"2023": 1}


def test_aggregate_history_preserves_record_currency_per_year() -> None:
    history = DividendHistory.of(
        [
            _record(fiscal_year="2022", amount=0.5, currency="HKD"),
            _record(fiscal_year="2022", amount=0.3, currency="HKD"),
        ],
    )
    track = aggregate_history(history)
    fy22 = track.get("2022")
    assert fy22 is not None
    assert fy22.amount == pytest.approx(0.8)
    assert fy22.currency == "HKD"
    assert dict(track.annual_distribution_counts) == {"2022": 2}


# --------------------------------------------------------------------------- #
# compute_dividend_ratios
# --------------------------------------------------------------------------- #


def _track(*pairs: tuple[str, float], currency: str = "CNY") -> DividendTrackRecord:
    dps = tuple((y, DividendPerShare(v, currency)) for y, v in pairs)
    counts = tuple((y, 1) for y, _ in pairs)
    return DividendTrackRecord(annual_dps=dps, annual_distribution_counts=counts)


def test_compute_dividend_ratios_blank_for_empty_track_record() -> None:
    ratios = compute_dividend_ratios(
        DividendTrackRecord.empty(),
        annual_eps={"2023": 1.0},
        current_price=10.0,
    )
    assert ratios.payout_pairs == ()
    assert ratios.avg_payout is None
    assert ratios.latest_yield is None


def test_compute_dividend_ratios_skips_year_without_usable_inputs() -> None:
    track = _track(("2023", 0.5))

    bad_eps = compute_dividend_ratios(track, {"2023": -1.0}, current_price=10.0)
    assert bad_eps.payout_pairs == ()

    missing_eps = compute_dividend_ratios(track, {}, current_price=10.0)
    assert missing_eps.payout_pairs == ()


def test_compute_dividend_ratios_yields_latest_only_when_price_is_known() -> None:
    track = _track(("2023", 1.0))

    no_price = compute_dividend_ratios(
        track,
        annual_eps={"2023": 0.5},
        current_price=None,
    )
    assert len(no_price.payout_pairs) == 1
    assert no_price.payout_pairs[0][1].value == 2.0
    assert no_price.latest_yield is None

    priced = compute_dividend_ratios(
        track,
        annual_eps={"2023": 0.5},
        current_price=20.0,
    )
    assert priced.latest_yield is not None
    assert priced.latest_yield.value == 0.05


def test_compute_dividend_ratios_drops_years_outside_history_window() -> None:
    recent = str(datetime.now().year - 1)
    track = _track(("2010", 0.5), (recent, 0.5))
    eps = {"2010": 1.0, recent: 1.0}

    ratios = compute_dividend_ratios(
        track, eps, current_price=10.0, history_years=5
    )
    years = [year for year, _ in ratios.payout_pairs]
    assert "2010" not in years
    assert recent in years


def test_compute_dividend_ratios_emits_per_year_pairs_with_average_and_latest() -> None:
    track = _track(("2022", 0.2), ("2023", 0.3), ("2024", 0.4))
    eps = {"2022": 0.5, "2023": 0.5, "2024": 0.5}

    ratios = compute_dividend_ratios(
        track,
        eps,
        current_price=10.0,
        history_years=100,
    )

    payout_values = [round(r.value, 4) for _, r in ratios.payout_pairs]
    assert payout_values == [0.4, 0.6, 0.8]

    assert ratios.avg_payout is not None
    assert ratios.avg_payout.value == pytest.approx(0.6, abs=1e-6)
    assert ratios.latest_yield is not None
    assert ratios.latest_yield.value == 0.04


def test_compute_dividend_ratios_payout_ignores_share_count_change() -> None:
    """DPS / EPS cancels weighted-average shares, so a stock split has no effect."""
    track_pre_split = _track(("2024", 1.0))
    track_post_split = _track(("2024", 0.5))

    ratios_pre = compute_dividend_ratios(
        track_pre_split, {"2024": 2.0}, current_price=20.0
    )
    ratios_post = compute_dividend_ratios(
        track_post_split, {"2024": 1.0}, current_price=10.0
    )

    assert ratios_pre.payout_pairs[0][1].value == ratios_post.payout_pairs[0][1].value
