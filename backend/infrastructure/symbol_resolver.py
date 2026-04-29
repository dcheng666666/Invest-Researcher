"""Map raw user/API stock symbols to canonical ``Symbol`` values."""

from __future__ import annotations

from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol


def parse_symbol(symbol: str) -> Symbol:
    """Map user/API input to a canonical ``Symbol``.

    - Six-digit numeric codes are A-shares (SH/SZ).
    - One- to five-digit numeric codes are zero-padded to five and treated as HK.
    - Accepts ``HK00700``, ``00700.HK`` (case-insensitive).
    - Accepts A-share prefixes ``SH600519`` / ``SZ000333``.
    - BSE (Beijing Stock Exchange) listings are not currently supported.
    """
    s = symbol.strip().upper().replace(" ", "")
    if s.startswith("HK") and len(s) > 2:
        tail = s[2:].removesuffix(".HK")
        if tail.isdigit():
            return Symbol(code=tail.zfill(5), market=Market.HK)
    if s.endswith(".HK"):
        base = s[:-3]
        if base.isdigit():
            return Symbol(code=base.zfill(5), market=Market.HK)
    if s.startswith("SH") and len(s) == 8 and s[2:].isdigit():
        return Symbol(code=s[2:], market=Market.A)
    if s.startswith("SZ") and len(s) == 8 and s[2:].isdigit():
        return Symbol(code=s[2:], market=Market.A)
    if s.isdigit():
        if len(s) == 6:
            return Symbol(code=s, market=Market.A)
        return Symbol(code=s.zfill(5), market=Market.HK)
    return Symbol(code=symbol.strip(), market=Market.A)
