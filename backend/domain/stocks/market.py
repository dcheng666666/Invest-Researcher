"""Market value object: the broad regulatory area a security trades in."""

from __future__ import annotations

from enum import Enum

__all__ = ["Market"]


class Market(str, Enum):
    """Coarse-grained market classification.

    Subclasses ``str`` so that legacy comparisons like ``mkt == "HK"``
    keep working while we migrate callers towards the enum.
    """

    A = "A"
    HK = "HK"

    @property
    def default_currency(self) -> str:
        return "HKD" if self is Market.HK else "CNY"

    @property
    def default_region(self) -> str:
        return "HK" if self is Market.HK else "CN"
