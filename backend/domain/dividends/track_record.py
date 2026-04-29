"""DividendTrackRecord: per-fiscal-year aggregated cash DPS."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.dividends.amounts import DividendPerShare

__all__ = ["DividendTrackRecord"]


@dataclass(frozen=True)
class DividendTrackRecord:
    """Cash dividend per share, summed per fiscal year, sorted ascending.

    ``annual_distribution_counts`` counts cash (and special cash) dividend
    records that contributed to each fiscal year, aligned with ``annual_dps``.
    """

    annual_dps: tuple[tuple[str, DividendPerShare], ...]
    annual_distribution_counts: tuple[tuple[str, int], ...]

    @classmethod
    def empty(cls) -> "DividendTrackRecord":
        return cls(annual_dps=(), annual_distribution_counts=())

    @property
    def is_empty(self) -> bool:
        return len(self.annual_dps) == 0

    def years(self) -> list[str]:
        return [y for y, _ in self.annual_dps]

    def get(self, year: str) -> DividendPerShare | None:
        for y, dps in self.annual_dps:
            if y == year:
                return dps
        return None
