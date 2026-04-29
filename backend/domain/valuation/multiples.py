"""Valuation-multiple value objects.

All concrete multiples (PE / PB / PS / PEG) implement the ``ValuationMultiple``
protocol, which exposes a single ``value: float`` attribute. Each multiple
carries enough metadata (e.g. ``EarningsBasis`` for earnings-anchored ones)
that the surrounding code never has to guess which stream a number was
computed against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from backend.domain.quality.profitability import ReturnOnEquity
from backend.domain.valuation.basis import EarningsBasis

__all__ = [
    "ValuationMultiple",
    "PERatio",
    "PBRatio",
    "PSRatio",
    "PEGRatio",
]


@runtime_checkable
class ValuationMultiple(Protocol):
    """Common shape every valuation multiple must satisfy.

    Concrete multiples are immutable dataclasses; this protocol exists so
    callers (history projection, assessment, comparison) can treat them
    uniformly without coupling to a concrete subtype.
    """

    value: float


@dataclass(frozen=True)
class PERatio:
    """Price / Earnings, anchored to a specific earnings basis (TTM/Forward/...)."""

    value: float
    basis: EarningsBasis = EarningsBasis.TTM

    @classmethod
    def from_market_cap(
        cls,
        market_cap: float | None,
        earnings: float | None,
        *,
        basis: EarningsBasis = EarningsBasis.TTM,
    ) -> "PERatio | None":
        if not market_cap or not earnings or earnings <= 0:
            return None
        return cls(value=market_cap / earnings, basis=basis)

    def compute_pb(self, roe: ReturnOnEquity) -> "PBRatio | None":
        # PB = PE * ROE only holds when ROE is positive; falls back to None
        # so the caller can defer to a direct book-value computation.
        latest = roe.latest()
        if latest is None or latest <= 0:
            return None
        return PBRatio(value=self.value * latest)


@dataclass(frozen=True)
class PBRatio:
    """Price / Book ratio."""

    value: float

    @classmethod
    def from_market_cap(
        cls,
        market_cap: float | None,
        book_value: float | None,
    ) -> "PBRatio | None":
        if not market_cap or not book_value or book_value <= 0:
            return None
        return cls(value=market_cap / book_value)


@dataclass(frozen=True)
class PSRatio:
    """Price / Sales ratio (sales basis defaults to trailing twelve months)."""

    value: float
    basis: EarningsBasis = EarningsBasis.TTM

    @classmethod
    def from_market_cap(
        cls,
        market_cap: float | None,
        revenue: float | None,
        *,
        basis: EarningsBasis = EarningsBasis.TTM,
    ) -> "PSRatio | None":
        if not market_cap or not revenue or revenue <= 0:
            return None
        return cls(value=market_cap / revenue, basis=basis)


@dataclass(frozen=True)
class PEGRatio:
    """``PEG = PE / (annual growth rate expressed as percent)``.

    Inherits the ``EarningsBasis`` from the underlying ``PERatio`` so that
    forward-PE-driven PEGs are not silently mixed with TTM-PE-driven ones.
    """

    value: float
    basis: EarningsBasis = EarningsBasis.TTM

    @classmethod
    def from_pe(
        cls, pe: PERatio | None, avg_growth_rate: float | None
    ) -> "PEGRatio | None":
        if pe is None or avg_growth_rate is None or avg_growth_rate <= 0:
            return None
        return cls(value=pe.value / (avg_growth_rate * 100), basis=pe.basis)
