"""Stock symbol value object."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.stocks.market import Market

__all__ = ["Symbol"]


@dataclass(frozen=True)
class Symbol:
    code: str
    market: Market

    def __str__(self) -> str:
        return f"{self.code}.{self.market.value}"
