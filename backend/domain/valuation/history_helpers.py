"""Cross-aggregate helpers used to seed ``ValuationHistory`` / ``ValuationSnapshot``.

Kept separate from ``history.py`` so that ``snapshot.py`` can consume these
helpers without pulling in the ``ValuationHistory`` aggregate (which itself
imports ``ValuationSnapshot``).
"""

from __future__ import annotations

from backend.domain.financials.history import FinancialHistory

__all__ = ["ttm_profit_timeline_from_history"]


def ttm_profit_timeline_from_history(
    history: FinancialHistory,
) -> list[tuple[str, float]]:
    """Build ``("YYYY-MM", ttm_profit)`` timeline for valuation use-cases."""
    return [
        (f"{period.fiscal_year}-{period.period_end.month:02d}", ttm_profit)
        for period, ttm_profit in history.ttm_series("net_profit_deducted").pairs
    ]
