"""Report-period value object.

A ``ReportPeriod`` identifies a single fiscal reporting interval. The codebase
currently only ingests quarterly filings (Q4 == full-year report), so we keep
the shape small: ``fiscal_year`` + ``quarter`` (1..4) + the real ``period_end``
date so calendar-accurate spans can be computed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import total_ordering

__all__ = ["ReportPeriod"]


@total_ordering
@dataclass(frozen=True)
class ReportPeriod:
    fiscal_year: int
    quarter: int
    period_end: date

    def __post_init__(self) -> None:
        if self.quarter not in (1, 2, 3, 4):
            raise ValueError(f"quarter must be 1..4, got {self.quarter}")

    @classmethod
    def quarterly(cls, fiscal_year: int, quarter: int, period_end: date) -> "ReportPeriod":
        return cls(fiscal_year=fiscal_year, quarter=quarter, period_end=period_end)

    @property
    def label(self) -> str:
        return f"{self.fiscal_year}Q{self.quarter}"

    @property
    def is_annual(self) -> bool:
        """Q4 marks the full-year report under our current data sources."""
        return self.quarter == 4

    def years_until(self, other: "ReportPeriod") -> float:
        """Calendar-year distance between two period ends."""
        return (other.period_end - self.period_end).days / 365.25

    def _sort_key(self) -> tuple[int, int]:
        return (self.fiscal_year, self.quarter)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ReportPeriod):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    def __str__(self) -> str:
        return self.label
