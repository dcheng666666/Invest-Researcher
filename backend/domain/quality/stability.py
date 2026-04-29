"""Stability value object: cross-period dispersion of profitability and earnings.

Quality signal: low dispersion ⇒ predictable / moaty business; high dispersion
⇒ cyclical or fragile economics. All measurements operate on annual-only
views to filter out quarterly seasonality (which would otherwise dominate
the dispersion).

Three evaluation dimensions, mirroring the design:

1. **ROE consistency** — ``roe_stddev`` in percentage points.
2. **Margin stability** — ``gross_margin_stddev`` and ``net_margin_stddev``,
   both in percentage points.
3. **Earnings volatility** — ``earnings_growth_volatility``: CV of YoY
   net-profit growth rates. Strips out the long-term growth trend so a
   steady compounder reads as low volatility; only year-to-year instability
   shows up. ``earnings_coefficient_of_variation`` exposes the raw level CV
   for transparency but is NOT the headline metric.

Stddev is the natural unit for ratio series (already percentage); CV
normalises the absolute net-profit series whose scale varies by orders of
magnitude across companies.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence

from backend.domain.financials.history import FinancialHistory
from backend.domain.financials.series import FinancialSeries

__all__ = ["Stability"]


_NEAR_ZERO = 1e-9


def _stddev(values: Sequence[float]) -> float | None:
    """Sample standard deviation (Bessel-corrected). ``None`` for n < 2."""
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def _coefficient_of_variation(values: Sequence[float]) -> float | None:
    """``stddev / |mean|``. ``None`` when n < 2 or |mean| is below numerical
    noise (CV is undefined / unstable in that regime)."""
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    if abs(mean) < _NEAR_ZERO:
        return None
    return statistics.stdev(values) / abs(mean)


@dataclass(frozen=True)
class Stability:
    """Quarter-aligned ratio + earnings series with dispersion behaviors.

    The four held series are:
    - ``roe`` / ``gross_margin`` / ``net_margin``: per-period ratios as
      reported. Dispersion is computed on the ``annual_only`` view (Q4
      entries) to avoid mixing quarterly seasonal noise into the signal.
    - ``annual_net_profit``: full-year net profit at Q4 boundaries, derived
      via ``history.ttm_series('net_profit').annual_only()``. The TTM step
      gives a single cross-market definition (A-share YTD or HK discrete both
      collapse to the trailing-four-quarter sum).
    """

    roe: FinancialSeries
    gross_margin: FinancialSeries
    net_margin: FinancialSeries
    annual_net_profit: FinancialSeries

    @classmethod
    def from_history(cls, history: FinancialHistory) -> "Stability":
        return cls(
            roe=history.metric_series("roe"),
            gross_margin=history.metric_series("gross_margin"),
            net_margin=history.metric_series("net_margin"),
            annual_net_profit=history.ttm_series("net_profit").annual_only(),
        )

    # ------------------------------------------------------------------ #
    # ROE consistency
    # ------------------------------------------------------------------ #

    def roe_stddev(self) -> float | None:
        """Sample stddev of annual ROE in percentage points (e.g. ``0.03`` =
        3pp). Lower ⇒ more consistent earning-power; ~3pp is typical for
        moaty businesses, >7pp signals cyclicality."""
        return _stddev(self.roe.annual_only().values)

    # ------------------------------------------------------------------ #
    # Margin stability
    # ------------------------------------------------------------------ #

    def gross_margin_stddev(self) -> float | None:
        """Sample stddev of annual gross margin in percentage points. A
        moaty business with pricing power keeps gross margin tight; commodity
        businesses see it swing with input prices."""
        return _stddev(self.gross_margin.annual_only().values)

    def net_margin_stddev(self) -> float | None:
        """Sample stddev of annual net margin in percentage points. Captures
        the combined effect of gross margin swings, operating leverage and
        non-operating items below the line."""
        return _stddev(self.net_margin.annual_only().values)

    # ------------------------------------------------------------------ #
    # Earnings volatility
    # ------------------------------------------------------------------ #

    def earnings_growth_volatility(self) -> float | None:
        """CV of YoY net-profit growth rates — the assessment-grade scalar
        for "earnings volatility".

        Why this and not CV of NP levels: a steadily compounding business
        (e.g. NP 270 → 860 亿 over 9 years with smooth ~15% YoY) will show
        a *level* CV near 40% just from the upward trend. That trend itself
        is a sign of quality, not volatility. Computing CV on YoY growth
        rates strips out the trend and leaves only the year-to-year
        instability.

        Periods where the prior-year NP is non-positive are dropped (growth
        rate is mathematically unstable there). Returns ``None`` when fewer
        than two valid growth observations exist.
        """
        levels = self.annual_net_profit.values
        if len(levels) < 3:
            return None
        growth_rates: list[float] = []
        for prev, curr in zip(levels, levels[1:]):
            if prev <= 0:
                continue
            growth_rates.append((curr - prev) / prev)
        return _coefficient_of_variation(growth_rates)

    def earnings_coefficient_of_variation(self) -> float | None:
        """CV of annual net-profit *levels* — exposed for transparency /
        charting only. Encodes growth and noise together, so even a clean
        compounder will read non-trivial. Use ``earnings_growth_volatility``
        as the assessment-grade scalar."""
        return _coefficient_of_variation(self.annual_net_profit.values)
