"""Exchange value object: a concrete venue a security is listed on."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol

__all__ = ["Exchange", "SSE", "SZSE", "HKEX", "exchange_for_symbol"]


@dataclass(frozen=True)
class Exchange:
    """A specific listing venue (e.g. SSE, SZSE, HKEX).

    ``Market`` describes the broad regulatory area; ``Exchange`` pins down
    the concrete venue plus its trading currency.
    """

    code: str
    name: str
    market: Market
    currency: str


SSE = Exchange("SSE", "Shanghai Stock Exchange", Market.A, "CNY")
SZSE = Exchange("SZSE", "Shenzhen Stock Exchange", Market.A, "CNY")
HKEX = Exchange("HKEX", "Hong Kong Stock Exchange", Market.HK, "HKD")


def exchange_for_symbol(symbol: Symbol) -> Exchange:
    """Resolve the listing venue from the canonical ``Symbol``.

    A-share venue is inferred from the leading digit per Chinese market
    conventions (6→SSE, 0/3→SZSE). BSE (Beijing Stock Exchange) listings
    are not currently supported and fall back to SSE.
    """
    if symbol.market is Market.HK:
        return HKEX
    head = symbol.code[:1]
    if head == "6":
        return SSE
    if head in {"0", "3"}:
        return SZSE
    return SSE
