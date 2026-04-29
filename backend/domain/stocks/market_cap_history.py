"""Monthly market-cap history value objects (in raw yuan)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

__all__ = ["MarketCapPoint", "MarketCapHistory"]


@dataclass(frozen=True)
class MarketCapPoint:
    """A single ``(YYYY-MM, market_cap)`` observation in raw yuan."""

    period: str
    market_cap: float


@dataclass(frozen=True)
class MarketCapHistory:
    """Chronologically ordered monthly market-cap series, all values in yuan.

    The series carries one point per calendar month (caller is responsible
    for picking month-end / month-average semantics upstream). Construct
    via ``from_pairs`` to get NaN/None filtering and sort+dedupe by period.
    """

    points: tuple[MarketCapPoint, ...] = field(default_factory=tuple)

    @classmethod
    def from_pairs(
        cls, pairs: Iterable[tuple[str, float]]
    ) -> "MarketCapHistory":
        """Build a history from ``(period, yuan)`` pairs, last write wins per period."""
        cleaned: dict[str, float] = {}
        for period, value in pairs:
            if not period:
                continue
            try:
                value_f = float(value)
            except (TypeError, ValueError):
                continue
            if math.isnan(value_f):
                continue
            cleaned[str(period)] = value_f
        ordered = sorted(cleaned.items(), key=lambda kv: kv[0])
        return cls(points=tuple(MarketCapPoint(p, v) for p, v in ordered))

    def is_empty(self) -> bool:
        return not self.points

    def as_pairs(self) -> list[tuple[str, float]]:
        """Return ``(period, market_cap_yuan)`` pairs for downstream consumers."""
        return [(p.period, p.market_cap) for p in self.points]
