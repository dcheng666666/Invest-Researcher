"""Time-sensitive market snapshot for a stock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain.stocks.symbol import Symbol

__all__ = ["StockSnapshot"]


@dataclass(frozen=True)
class StockSnapshot:
    """Market-quote attributes at a point in time.

    Carries its owning ``Symbol`` so a snapshot is self-describing and
    can be aggregated under the right ``Security`` even when passed
    around independently.
    """

    symbol: Symbol
    current_price: float | None
    market_cap: float | None
    total_shares: float | None
    as_of: datetime
