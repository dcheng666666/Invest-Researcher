"""Profitability value objects.

Each ratio (ROE, ROA, gross/net margin) is wrapped in a small VO with a
uniform interface (``latest`` / ``average`` / ``years_above`` / annual view).
``Profitability`` aggregates the four into the company-level earning-power
picture consumed by ``QualityEvaluator``.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.financials.history import FinancialHistory
from backend.domain.financials.series import FinancialSeries

__all__ = [
    "ReturnOnEquity",
    "ReturnOnAssets",
    "GrossMargin",
    "NetMargin",
    "Profitability",
]


@dataclass(frozen=True)
class _RatioMetric:
    """Quarterly decimal-ratio series (``0.15`` == 15%) with annual-only view.

    Subclasses bind a specific ``FinancialMetrics`` attribute via their own
    ``from_history`` factory; the analytic helpers below are shared.
    """

    quarterly: FinancialSeries

    @property
    def annual(self) -> FinancialSeries:
        return self.quarterly.annual_only()

    def latest(self) -> float | None:
        last = self.quarterly.latest()
        return last[1] if last else None

    def average(self, *, annual_only: bool = True) -> float | None:
        series = self.annual if annual_only else self.quarterly
        if not series:
            return None
        return sum(series.values) / len(series)

    def years_above(self, threshold: float, *, annual_only: bool = True) -> int:
        series = self.annual if annual_only else self.quarterly
        return sum(1 for v in series.values if v >= threshold)

    def annual_period_count(self) -> int:
        return len(self.annual)


@dataclass(frozen=True)
class ReturnOnEquity(_RatioMetric):
    """Net profit / shareholders' equity. Built from ``metrics.roe``."""

    @classmethod
    def from_history(cls, history: FinancialHistory) -> "ReturnOnEquity":
        return cls(quarterly=history.metric_series("roe"))


@dataclass(frozen=True)
class ReturnOnAssets(_RatioMetric):
    """Net profit / total assets. Built from ``metrics.roa``.

    Strips out the leverage component of ROE: a high ROE backed by a low ROA
    means the equity return is largely a function of the debt structure.
    """

    @classmethod
    def from_history(cls, history: FinancialHistory) -> "ReturnOnAssets":
        return cls(quarterly=history.metric_series("roa"))


@dataclass(frozen=True)
class GrossMargin(_RatioMetric):
    """Gross profit / revenue. Built from ``metrics.gross_margin``."""

    @classmethod
    def from_history(cls, history: FinancialHistory) -> "GrossMargin":
        return cls(quarterly=history.metric_series("gross_margin"))


@dataclass(frozen=True)
class NetMargin(_RatioMetric):
    """Net profit / revenue. Built from ``metrics.net_margin``."""

    @classmethod
    def from_history(cls, history: FinancialHistory) -> "NetMargin":
        return cls(quarterly=history.metric_series("net_margin"))


@dataclass(frozen=True)
class Profitability:
    """Aggregate earning-power view across the four core profitability ratios.

    Composed (not inherited) from the per-ratio VOs so each retains its own
    domain identity (e.g. ``ReturnOnEquity`` is still meaningful in valuation
    snapshots) while ``Profitability`` provides the single entry point quality
    evaluation needs.
    """

    roe: ReturnOnEquity
    roa: ReturnOnAssets
    gross_margin: GrossMargin
    net_margin: NetMargin

    @classmethod
    def from_history(cls, history: FinancialHistory) -> "Profitability":
        return cls(
            roe=ReturnOnEquity.from_history(history),
            roa=ReturnOnAssets.from_history(history),
            gross_margin=GrossMargin.from_history(history),
            net_margin=NetMargin.from_history(history),
        )
