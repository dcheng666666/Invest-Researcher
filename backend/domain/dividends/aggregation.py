"""Aggregate a DividendHistory into a per-fiscal-year DividendTrackRecord."""

from __future__ import annotations

from backend.domain.dividends.amounts import DividendPerShare
from backend.domain.dividends.history import DividendHistory
from backend.domain.dividends.track_record import DividendTrackRecord

__all__ = ["aggregate_history"]


def aggregate_history(history: DividendHistory) -> DividendTrackRecord:
    """Sum cash dividend per share by the fiscal year tagged on each record."""
    if history.is_empty:
        return DividendTrackRecord.empty()

    fy_amounts: dict[str, float] = {}
    fy_currency: dict[str, str] = {}
    fy_counts: dict[str, int] = {}

    for record in history.records:
        if not record.is_cash:
            continue
        amount = record.dividend_per_share.amount
        if amount <= 0:
            continue
        fiscal_year = record.fiscal_year
        fy_amounts[fiscal_year] = fy_amounts.get(fiscal_year, 0.0) + amount
        fy_currency.setdefault(fiscal_year, record.dividend_per_share.currency)
        fy_counts[fiscal_year] = fy_counts.get(fiscal_year, 0) + 1

    sorted_years = sorted(fy_amounts)
    annual = tuple(
        (year, DividendPerShare(amount=fy_amounts[year], currency=fy_currency[year]))
        for year in sorted_years
    )
    annual_counts = tuple((year, fy_counts[year]) for year in sorted_years)
    return DividendTrackRecord(
        annual_dps=annual,
        annual_distribution_counts=annual_counts,
    )
