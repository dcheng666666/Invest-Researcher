"""Historical valuation timeline aggregate.

``ValuationHistory`` aggregates a chronologically ordered set of
``ValuationSnapshot`` value objects. Distribution helpers (band /
percentile) accept a metric projection so the same aggregate can serve
PE / PB / PS / dividend-yield analyses without duplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from backend.domain.valuation.band import HistoricalBand, Percentile
from backend.domain.valuation.basis import EarningsBasis
from backend.domain.valuation.history_helpers import ttm_profit_timeline_from_history
from backend.domain.valuation.multiples import PERatio
from backend.domain.valuation.snapshot import ValuationSnapshot

__all__ = ["ValuationHistory", "ttm_profit_timeline_from_history"]


# A metric projection turns a snapshot into a comparable scalar (e.g. PE
# value). Returning ``None`` lets us skip points where the metric was not
# observed. PE / PB / PS / dividend-yield projections are bundled below.
MetricProjection = Callable[[ValuationSnapshot], float | None]


def pe_metric(snapshot: ValuationSnapshot) -> float | None:
    return snapshot.pe_value


def pb_metric(snapshot: ValuationSnapshot) -> float | None:
    return snapshot.pb_value


def ps_metric(snapshot: ValuationSnapshot) -> float | None:
    return snapshot.ps_value


def dividend_yield_metric(snapshot: ValuationSnapshot) -> float | None:
    return snapshot.dividend_yield


@dataclass(frozen=True)
class ValuationHistory:
    """Chronologically ordered sequence of historical ``ValuationSnapshot`` records.

    Constructed today from monthly market-cap data plus the rolling TTM
    profit timeline (both in raw yuan); only ``pe_ratio`` is populated for
    backfill snapshots until richer historical fields (book value,
    revenue, ...) are wired in.
    """

    snapshots: tuple[ValuationSnapshot, ...]

    @classmethod
    def from_inputs(
        cls,
        market_cap_monthly: list[tuple[str, float]],
        ttm_profit_timeline: list[tuple[str, float]],
    ) -> "ValuationHistory":
        if not market_cap_monthly or not ttm_profit_timeline:
            return cls(snapshots=tuple())

        records: list[ValuationSnapshot] = []
        ttm_idx = 0
        for period, market_cap in market_cap_monthly:
            while (
                ttm_idx < len(ttm_profit_timeline) - 1
                and ttm_profit_timeline[ttm_idx + 1][0] <= period
            ):
                ttm_idx += 1
            if ttm_profit_timeline[ttm_idx][0] > period:
                continue
            profit = ttm_profit_timeline[ttm_idx][1]
            if not profit or profit <= 0:
                continue
            pe_value = market_cap / profit
            # Drop pathological PE points (negative earnings already caught
            # above, so we only need to clip the upper tail).
            if not (0 < pe_value < 500):
                continue
            records.append(
                ValuationSnapshot(
                    as_of_date=_parse_period(period),
                    price=None,
                    market_cap=market_cap,
                    pe_ratio=PERatio(value=round(pe_value, 2), basis=EarningsBasis.TTM),
                    pb_ratio=None,
                    ps_ratio=None,
                )
            )
        return cls(snapshots=tuple(records))

    def is_empty(self) -> bool:
        return not self.snapshots

    def with_seed(self, period: str, pe: float) -> "ValuationHistory":
        """Return a copy seeded with a single fallback ``(period, pe)`` point."""
        seed = ValuationSnapshot(
            as_of_date=_parse_period(period),
            price=None,
            market_cap=None,
            pe_ratio=PERatio(value=round(pe, 2), basis=EarningsBasis.TTM),
            pb_ratio=None,
            ps_ratio=None,
        )
        return ValuationHistory(snapshots=(seed,))

    # ---------- Metric projections ----------

    def metric_values(self, projection: MetricProjection = pe_metric) -> list[float]:
        return [v for v in (projection(s) for s in self.snapshots) if v is not None]

    def metric_pairs(
        self, projection: MetricProjection = pe_metric
    ) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for s in self.snapshots:
            v = projection(s)
            if v is None:
                continue
            out.append((_format_period(s.as_of_date), v))
        return out

    def band(
        self, projection: MetricProjection = pe_metric
    ) -> HistoricalBand | None:
        return HistoricalBand.from_values(self.metric_values(projection))

    def percentile_of(
        self,
        current: float | None,
        projection: MetricProjection = pe_metric,
    ) -> Percentile | None:
        return Percentile.of(self.metric_values(projection), current)


def _parse_period(period: str) -> datetime:
    """Parse a ``"YYYY-MM"`` label into a ``datetime`` anchored at the 1st."""
    try:
        return datetime.strptime(period, "%Y-%m")
    except ValueError:
        return datetime.fromisoformat(period)


def _format_period(moment: datetime) -> str:
    return f"{moment.year}-{moment.month:02d}"
