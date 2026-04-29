"""Point-in-time valuation snapshot value object.

A ``ValuationSnapshot`` is the canonical projection of "what does this
business look like as a market security at a given moment". It is the unit
that ``ValuationHistory`` aggregates, so the same shape powers both the
current quote and any historical replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain.financials.history import FinancialHistory
from backend.domain.quality.profitability import ReturnOnEquity
from backend.domain.stocks.snapshot import StockSnapshot
from backend.domain.valuation.basis import EarningsBasis
from backend.domain.valuation.history_helpers import ttm_profit_timeline_from_history
from backend.domain.valuation.multiples import PBRatio, PERatio, PSRatio

__all__ = ["ValuationSnapshot"]


@dataclass(frozen=True)
class ValuationSnapshot:
    """Fully resolved valuation state at a moment in time.

    Field set follows the canonical valuation modeling: the snapshot is
    intentionally narrow and contains only attributes that are directly
    observable for the ``as_of_date``. Composite/derived multiples (e.g.
    PEG) belong on the surrounding application/service layer because they
    pull in non-snapshot signals (growth rates, comparables).
    """

    as_of_date: datetime
    price: float | None
    market_cap: float | None
    pe_ratio: PERatio | None
    pb_ratio: PBRatio | None
    ps_ratio: PSRatio | None
    ev_ebit: float | None = None
    dividend_yield: float | None = None

    @classmethod
    def from_inputs(
        cls,
        stock_snapshot: StockSnapshot,
        history: FinancialHistory,
        roe: ReturnOnEquity,
        *,
        dividend_yield: float | None = None,
        ev_ebit: float | None = None,
    ) -> "ValuationSnapshot":
        """Compose the latest snapshot from a stock quote + financial history.

        ``ev_ebit`` and ``dividend_yield`` stay opt-in because they require
        signals (enterprise value, dividend stream) outside what
        ``FinancialHistory`` carries.
        """
        market_cap = stock_snapshot.market_cap
        total_shares = stock_snapshot.total_shares
        price = stock_snapshot.current_price
        if not price and market_cap and total_shares:
            price = market_cap / total_shares

        ttm_profit_timeline = ttm_profit_timeline_from_history(history)
        latest_ttm_profit = ttm_profit_timeline[-1][1] if ttm_profit_timeline else None
        pe_ratio = PERatio.from_market_cap(
            market_cap, latest_ttm_profit, basis=EarningsBasis.TTM
        )
        pb_ratio = pe_ratio.compute_pb(roe) if pe_ratio is not None else None

        latest_ttm_revenue = _latest_ttm_revenue(history)
        ps_ratio = PSRatio.from_market_cap(
            market_cap, latest_ttm_revenue, basis=EarningsBasis.TTM
        )

        return cls(
            as_of_date=stock_snapshot.as_of,
            price=price,
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            ps_ratio=ps_ratio,
            ev_ebit=ev_ebit,
            dividend_yield=dividend_yield,
        )

    @property
    def pe_value(self) -> float | None:
        return self.pe_ratio.value if self.pe_ratio is not None else None

    @property
    def pb_value(self) -> float | None:
        return self.pb_ratio.value if self.pb_ratio is not None else None

    @property
    def ps_value(self) -> float | None:
        return self.ps_ratio.value if self.ps_ratio is not None else None


def _latest_ttm_revenue(history: FinancialHistory) -> float | None:
    series = history.ttm_series("revenue")
    latest = series.latest()
    return latest[1] if latest else None
