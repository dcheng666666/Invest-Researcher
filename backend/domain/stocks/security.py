"""Security aggregate root: ties together symbol, venue, profile, company, snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from backend.domain.stocks.company import Company
from backend.domain.stocks.exchange import Exchange
from backend.domain.stocks.market import Market
from backend.domain.stocks.market_cap_history import MarketCapHistory
from backend.domain.stocks.profile import Profile
from backend.domain.stocks.snapshot import StockSnapshot
from backend.domain.stocks.symbol import Symbol

__all__ = ["Security"]


@dataclass(frozen=True)
class Security:
    """Aggregate root for a single tradable security.

    A ``Security`` has one ``Symbol``, lists on one ``Exchange`` (which
    pins down the ``Market`` and trading currency), exposes a ``Profile``
    for its static attributes, may reference a ``Company`` issuer, carries
    its latest ``StockSnapshot`` (point-in-time market quote) and an
    optional ``MarketCapHistory`` (monthly market-cap series in raw yuan).
    """

    symbol: Symbol
    exchange: Exchange
    profile: Profile
    company: Company | None = None
    latest_snapshot: StockSnapshot | None = None
    market_cap_history: MarketCapHistory = field(default_factory=MarketCapHistory)

    def __post_init__(self) -> None:
        if (
            self.latest_snapshot is not None
            and self.latest_snapshot.symbol != self.symbol
        ):
            raise ValueError(
                f"Snapshot symbol {self.latest_snapshot.symbol} does not "
                f"match security {self.symbol}"
            )

    @property
    def market(self) -> Market:
        return self.symbol.market

    @property
    def currency(self) -> str:
        return self.exchange.currency

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def industry(self) -> str | None:
        return self.company.industry if self.company is not None else None

    def with_market_cap_history(self, history: MarketCapHistory) -> "Security":
        return replace(self, market_cap_history=history)
