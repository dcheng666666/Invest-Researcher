"""FinancialReport entity: one filing for one security at one period."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.financials.accounting import AccountingContext
from backend.domain.financials.metrics import FinancialMetrics
from backend.domain.financials.period import ReportPeriod
from backend.domain.financials.statements import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
)
from backend.domain.stocks.symbol import Symbol

__all__ = ["FinancialReport"]


@dataclass(frozen=True)
class FinancialReport:
    """Single-period financial filing for a security.

    Identity is ``(security_id, period)``. Carries the three statements plus
    the accounting context that explains how to interpret them, with
    pre-computed/picked metrics on the side.
    """

    security_id: Symbol
    period: ReportPeriod
    accounting: AccountingContext
    income_statement: IncomeStatement
    balance_sheet: BalanceSheet
    cash_flow_statement: CashFlowStatement
    metrics: FinancialMetrics

    @property
    def identity(self) -> tuple[Symbol, ReportPeriod]:
        return (self.security_id, self.period)
