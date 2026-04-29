"""Accounting context value object: currency, standard, period presentation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["ReportingStandard", "PeriodPresentation", "AccountingContext"]


class ReportingStandard(str, Enum):
    CAS = "CAS"
    IFRS = "IFRS"
    US_GAAP = "US_GAAP"


class PeriodPresentation(str, Enum):
    """How upstream flow-statement rows are aggregated within a fiscal year.

    ``YTD_CUMULATIVE``: each row is **calendar year-to-date** through that
    quarter-end (typical THS A-share / CAS quarterly disclosure). Single-quarter
    flows are recovered by subtracting the prior quarter within the same calendar
    year (see ``FinancialHistory._single_quarter_map``).

    ``DISCRETE``: each row is already a **single-period** amount (one quarter).
    THS does not use this for primary statements. For Hong Kong, Eastmoney F10
    feeds publish **fiscal** YTD cumulants on the wire; ``eastmoney_hk``
    converts income and cash-flow lines to discrete quarters at ingest time,
    then stores reports with this flag so ``FinancialHistory`` does not
    subtract twice.
    """

    YTD_CUMULATIVE = "ytd_cumulative"
    DISCRETE = "discrete"


@dataclass(frozen=True)
class AccountingContext:
    currency: str
    standard: ReportingStandard
    period_presentation: PeriodPresentation
