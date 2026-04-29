"""Payout-ratio and dividend-yield computations against a DividendTrackRecord."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain.dividends.amounts import (
    DividendPerShare,
    DividendYield,
    PayoutRatio,
)
from backend.domain.dividends.track_record import DividendTrackRecord

__all__ = ["DividendRatios", "compute_dividend_ratios"]


@dataclass(frozen=True)
class DividendRatios:
    """Per-fiscal-year payout plus the latest dividend yield.

    Historical per-year dividend yield is intentionally absent: a yield
    series that pairs each year's DPS with *today's* price is not a real
    time series — only the latest entry would be self-consistent. We keep
    just ``latest_yield`` (latest DPS / current price) here.
    """

    payout_pairs: tuple[tuple[str, PayoutRatio], ...]
    avg_payout: PayoutRatio | None
    latest_yield: DividendYield | None


def _safe_yield(
    dps: DividendPerShare, current_price: float | None
) -> DividendYield | None:
    if not current_price or current_price <= 0:
        return None
    return DividendYield.of(dps, current_price)


def compute_dividend_ratios(
    track_record: DividendTrackRecord,
    annual_eps: dict[str, float],
    *,
    current_price: float | None = None,
    history_years: int = 10,
) -> DividendRatios:
    """Cross-multiply DPS / EPS to derive per-FY PayoutRatio + headline yield.

    Using DPS / EPS rather than ``dividend_total / net_profit`` makes the
    per-year payout ratio independent of any share count: the weighted-
    average share count cancels on both sides. EPS here should be on the
    same accounting basis as the upstream report (e.g. deducted-of-non-
    recurring-items in A-share, holder-profit in HK).
    """
    cutoff_year = str(datetime.now().year - history_years)

    payout_pairs: list[tuple[str, PayoutRatio]] = []

    for year, dps in track_record.annual_dps:
        if year < cutoff_year:
            continue
        eps = annual_eps.get(year)
        ratio = PayoutRatio.from_dps_eps(dps.amount, eps)
        if ratio is not None:
            payout_pairs.append((year, ratio))

    avg_payout: PayoutRatio | None = None
    if payout_pairs:
        avg_value = sum(r.value for _, r in payout_pairs) / len(payout_pairs)
        avg_payout = PayoutRatio(round(avg_value, 4))

    latest_yield: DividendYield | None = None
    if track_record.annual_dps:
        latest_dps = track_record.annual_dps[-1][1]
        latest_yield = _safe_yield(latest_dps, current_price)

    return DividendRatios(
        payout_pairs=tuple(payout_pairs),
        avg_payout=avg_payout,
        latest_yield=latest_yield,
    )
