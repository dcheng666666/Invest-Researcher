"""DividendRecord: a single declared distribution event."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.domain.dividends.amounts import DividendPerShare
from backend.domain.dividends.types import DividendType

__all__ = ["DividendRecord"]


@dataclass(frozen=True)
class DividendRecord:
    """One distribution event declared by a company.

    ``fiscal_year`` is mandatory: by the time a record reaches the domain it
    has already been resolved to the fiscal year it belongs to. The
    repository layer is responsible for that resolution (HK reads the
    ``财政年度`` column verbatim; A-share infers from the THS announcement
    date via an infrastructure helper).

    The date fields are optional because upstream sources differ in what
    they expose (THS A-share only ships the announcement date; Eastmoney HK
    additionally ships ex-date / payment date when available).
    """

    fiscal_year: str
    dividend_per_share: DividendPerShare
    dividend_type: DividendType = DividendType.CASH
    announcement_date: date | None = None
    ex_dividend_date: date | None = None
    payment_date: date | None = None

    def __post_init__(self) -> None:
        if not self.fiscal_year:
            raise ValueError("DividendRecord requires a non-empty fiscal_year")

    @property
    def is_cash(self) -> bool:
        return self.dividend_type.is_cash

    @property
    def currency(self) -> str:
        return self.dividend_per_share.currency
