"""Dividend type value object."""

from __future__ import annotations

from enum import Enum

__all__ = ["DividendType"]


class DividendType(str, Enum):
    """Kind of distribution declared in a dividend record.

    Subclasses ``str`` so legacy comparisons keep working while we migrate
    callers towards the enum.
    """

    CASH = "CASH"
    SPECIAL = "SPECIAL"
    STOCK = "STOCK"
    SCRIP = "SCRIP"
    OTHER = "OTHER"

    @property
    def is_cash(self) -> bool:
        """Cash-equivalent payouts that move shareholder wealth in currency."""
        return self in (DividendType.CASH, DividendType.SPECIAL)
