"""Unified context shared between all analysis steps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain.dividends.history import DividendHistory
from backend.domain.financials.history import FinancialHistory
from backend.domain.stocks.market import Market
from backend.domain.stocks.profile import Profile
from backend.domain.stocks.security import Security
from backend.domain.stocks.snapshot import StockSnapshot


@dataclass(frozen=True)
class AnalysisContext:
    """Everything an individual five-step analyzer needs about a single stock.

    The application service builds this once from repositories, then passes
    it to each step. Steps are pure functions of the context (plus an optional
    LLM client port).
    """

    code: str
    security: Security
    financials: FinancialHistory
    dividends: DividendHistory
    as_of: datetime

    @property
    def name(self) -> str:
        return self.security.name

    @property
    def market(self) -> Market:
        return self.security.market

    @property
    def industry(self) -> str | None:
        return self.security.industry

    @property
    def profile(self) -> Profile:
        return self.security.profile

    @property
    def snapshot(self) -> StockSnapshot:
        latest = self.security.latest_snapshot
        if latest is None:
            raise ValueError(
                f"Security {self.security.symbol} has no market snapshot yet"
            )
        return latest
