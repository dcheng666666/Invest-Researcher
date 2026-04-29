"""DividendHistory aggregate root: a security's declared dividend records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.domain.dividends.record import DividendRecord

__all__ = ["DividendHistory"]


@dataclass(frozen=True)
class DividendHistory:
    """Per-security ordered collection of ``DividendRecord`` entries.

    Invariants enforced at construction:
    1. All records share a single currency, so cross-record DPS sums stay
       meaningful.

    Each ``DividendRecord`` already carries its resolved ``fiscal_year``
    (filled by the repository), so the aggregate root no longer needs to
    know which market the records came from.

    ``has_no_distribution`` preserves the upstream signal that a company
    explicitly chose not to distribute (THS marks rows as "不分配"); it is
    independent of ``records`` being empty.
    """

    records: tuple[DividendRecord, ...]
    has_no_distribution: bool = False

    def __post_init__(self) -> None:
        currencies = {r.dividend_per_share.currency for r in self.records}
        if len(currencies) > 1:
            raise ValueError(
                f"DividendHistory contains mixed currencies: {sorted(currencies)}"
            )

    @classmethod
    def empty(cls, has_no_distribution: bool = False) -> "DividendHistory":
        return cls(records=(), has_no_distribution=has_no_distribution)

    @classmethod
    def of(
        cls,
        records: Iterable[DividendRecord],
        has_no_distribution: bool = False,
    ) -> "DividendHistory":
        return cls(records=tuple(records), has_no_distribution=has_no_distribution)

    @property
    def is_empty(self) -> bool:
        return len(self.records) == 0

    @property
    def currency(self) -> str | None:
        if not self.records:
            return None
        return self.records[0].dividend_per_share.currency

    def cash_records(self) -> tuple[DividendRecord, ...]:
        return tuple(r for r in self.records if r.is_cash)
