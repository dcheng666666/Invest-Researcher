"""Financial-health value object: leverage + liquidity behaviors.

Holds annual-aware ``FinancialSeries`` for the leverage and liquidity
ratios published by the upstream feeds, plus the working-capital turnover
days carried over from the original skeleton (kept for back-compat with the
existing ``FinancialHealthResult`` payload (血液检查) — operationally these are
closer to operating-efficiency than balance-sheet health, but moving them
is out of scope for this VO's promotion).

The four core series surface:

- ``debt_ratio`` — leverage (total liab / total assets, decimal).
- ``current_ratio`` — short-term liquidity (multiple, e.g. ``1.5``).
- ``quick_ratio`` — stricter liquidity excluding inventory (multiple).
- ``cash_ratio`` — cash + equivalents / current liabilities (decimal).

Helper aggregations on annual-only views give a single scalar per metric
ready to be compared against signal thresholds. Returns ``None`` when the
annual view has no points (typical for HK where ``quick_ratio`` and
``cash_ratio`` are not surfaced).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.financials.history import FinancialHistory
from backend.domain.financials.series import FinancialSeries

__all__ = ["FinancialHealth"]


def _annual_average(series: FinancialSeries) -> float | None:
    annual = series.annual_only()
    if not annual:
        return None
    return sum(annual.values) / len(annual)


@dataclass(frozen=True)
class FinancialHealth:
    """Leverage + liquidity series with annual-average behavior helpers."""

    debt_ratio: FinancialSeries
    current_ratio: FinancialSeries
    quick_ratio: FinancialSeries
    cash_ratio: FinancialSeries
    receivable_turnover_days: FinancialSeries
    inventory_turnover_days: FinancialSeries

    @classmethod
    def from_history(cls, history: FinancialHistory) -> "FinancialHealth":
        return cls(
            debt_ratio=history.metric_series("debt_ratio"),
            current_ratio=history.metric_series("current_ratio"),
            quick_ratio=history.metric_series("quick_ratio"),
            cash_ratio=history.metric_series("cash_ratio"),
            receivable_turnover_days=history.metric_series("receivable_turnover_days"),
            inventory_turnover_days=history.metric_series("inventory_turnover_days"),
        )

    # ------------------------------------------------------------------ #
    # Annual-average aggregations consumed by quality signals.
    # ------------------------------------------------------------------ #

    def average_debt_ratio(self) -> float | None:
        return _annual_average(self.debt_ratio)

    def average_current_ratio(self) -> float | None:
        return _annual_average(self.current_ratio)

    def average_quick_ratio(self) -> float | None:
        return _annual_average(self.quick_ratio)

    def average_cash_ratio(self) -> float | None:
        return _annual_average(self.cash_ratio)
