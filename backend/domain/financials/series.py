"""Aligned (period, value) sequence value object.

``FinancialSeries`` is the primary cross-period view derived from a
``FinancialHistory`` (e.g. revenue across the last 10 years). Periods are
real ``ReportPeriod`` value objects so spans/CAGR are computed against the
underlying calendar dates rather than inferred from string suffixes.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Iterable, Iterator

from backend.domain.financials.period import ReportPeriod

__all__ = ["FinancialSeries"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FinancialSeries:
    pairs: tuple[tuple[ReportPeriod, float], ...] = ()

    @classmethod
    def of(
        cls, items: Iterable[tuple[ReportPeriod, float | None]]
    ) -> "FinancialSeries":
        kept: list[tuple[ReportPeriod, float]] = []
        for period, value in items:
            if value is None:
                logger.warning(
                    "FinancialSeries.of: skipped point (value is None), period=%s",
                    period.label,
                )
                continue
            try:
                fv = float(value)
            except (TypeError, ValueError):
                logger.warning(
                    "FinancialSeries.of: skipped point (value not coercible to float), "
                    "period=%s, value=%r",
                    period.label,
                    value,
                )
                continue
            if math.isnan(fv):
                logger.warning(
                    "FinancialSeries.of: skipped point (NaN), period=%s, raw=%r",
                    period.label,
                    value,
                )
                continue
            kept.append((period, fv))
        return cls(tuple(kept))

    def __iter__(self) -> Iterator[tuple[ReportPeriod, float]]:
        return iter(self.pairs)

    def __len__(self) -> int:
        return len(self.pairs)

    def __bool__(self) -> bool:
        return bool(self.pairs)

    def latest_n(self, n: int) -> "FinancialSeries":
        return FinancialSeries(self.pairs[-n:] if n > 0 else ())

    def annual_only(self) -> "FinancialSeries":
        return FinancialSeries(tuple((p, v) for p, v in self.pairs if p.is_annual))

    @property
    def values(self) -> list[float]:
        return [v for _, v in self.pairs]

    @property
    def periods(self) -> list[ReportPeriod]:
        return [p for p, _ in self.pairs]

    def latest(self) -> tuple[ReportPeriod, float] | None:
        return self.pairs[-1] if self.pairs else None

    def cagr(self) -> float | None:
        """End-to-end compound annual growth rate over the series.

        Falls back to linear annualization when the start/end value is
        non-positive (so we still get a readable number across sign flips).
        """
        if len(self.pairs) < 2:
            return None
        first_period, first_value = self.pairs[0]
        last_period, last_value = self.pairs[-1]
        span = first_period.years_until(last_period)
        if span <= 0 or first_value == 0:
            return None
        if first_value > 0 and last_value > 0:
            return (last_value / first_value) ** (1.0 / span) - 1.0
        return ((last_value - first_value) / abs(first_value)) / span
