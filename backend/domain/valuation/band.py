"""Historical valuation distribution helpers (band + percentile)."""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["HistoricalBand", "Percentile"]


@dataclass(frozen=True)
class HistoricalBand:
    """``mean ± 1σ`` band over a sorted sample, low-clipped to the observed min."""

    mean: float
    std_dev: float
    low: float
    high: float
    sample_size: int

    @classmethod
    def from_values(cls, values: list[float]) -> "HistoricalBand | None":
        sorted_values = sorted(values)
        if len(sorted_values) < 3:
            return None
        mean = sum(sorted_values) / len(sorted_values)
        variance = sum((v - mean) ** 2 for v in sorted_values) / len(sorted_values)
        std = math.sqrt(variance)
        low = round(max(mean - std, sorted_values[0]), 2)
        high = round(mean + std, 2)
        return cls(
            mean=round(mean, 2),
            std_dev=round(std, 2),
            low=low,
            high=high,
            sample_size=len(sorted_values),
        )


@dataclass(frozen=True)
class Percentile:
    """Fraction of historical values ``<= current`` (range 0..1)."""

    value: float
    sample_size: int

    @classmethod
    def of(cls, values: list[float], current: float | None) -> "Percentile | None":
        if not values or current is None:
            return None
        ratio = sum(1 for v in values if v <= current) / len(values)
        return cls(value=ratio, sample_size=len(values))
