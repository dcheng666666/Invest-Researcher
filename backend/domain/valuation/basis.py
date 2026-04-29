"""Earnings-basis enum: the semantic context attached to a PE multiple."""

from __future__ import annotations

from enum import Enum

__all__ = ["EarningsBasis"]


class EarningsBasis(str, Enum):
    """Which earnings stream a PE/PEG ratio is computed against.

    A PE without basis is ambiguous; carrying it lets us mix forward and
    historical numbers in the same domain object without conflating them.
    """

    # Trailing twelve months: sum of the four most recent reported quarters.
    # Backward-looking and audited, but lags structural changes in the business.
    TTM = "ttm"
    # Forward-looking estimate (typically next fiscal year consensus).
    # Reflects expectations but inherits analyst bias and revision risk.
    FORWARD = "forward"
    # Cycle-adjusted / through-the-cycle earnings (e.g. multi-year average or
    # mid-cycle margin x revenue). Smooths cyclicality so multiples stay
    # comparable across boom/bust periods.
    NORMALIZED = "normalized"
