"""Peer-comparable valuation set (relative-valuation building block).

Modeled as an immutable value object today; once a peer-data source is
wired in, this can be promoted to an aggregate that owns its own loading
and refresh semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.domain.stocks.symbol import Symbol
from backend.domain.valuation.history import (
    MetricProjection,
    pe_metric,
)
from backend.domain.valuation.snapshot import ValuationSnapshot

__all__ = ["ComparablePeer", "ComparableSet"]


@dataclass(frozen=True)
class ComparablePeer:
    """One peer in a comparable set: its identity + latest snapshot."""

    security_id: Symbol
    snapshot: ValuationSnapshot


@dataclass(frozen=True)
class ComparableSet:
    """Cross-section of peer snapshots used for relative-valuation analytics.

    Stays metric-agnostic: callers project the dimension they care about
    (PE / PB / PS / dividend-yield) via ``MetricProjection``.
    """

    peers: tuple[ComparablePeer, ...]

    @classmethod
    def of(cls, peers: Iterable[ComparablePeer]) -> "ComparableSet":
        return cls(peers=tuple(peers))

    def is_empty(self) -> bool:
        return not self.peers

    def values(
        self, projection: MetricProjection = pe_metric
    ) -> list[float]:
        return [
            v
            for v in (projection(p.snapshot) for p in self.peers)
            if v is not None
        ]

    def median(
        self, projection: MetricProjection = pe_metric
    ) -> float | None:
        vals = sorted(self.values(projection))
        if not vals:
            return None
        mid = len(vals) // 2
        if len(vals) % 2 == 1:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2

    def average(
        self, projection: MetricProjection = pe_metric
    ) -> float | None:
        vals = self.values(projection)
        if not vals:
            return None
        return sum(vals) / len(vals)
