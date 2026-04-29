"""Three-statement value objects: IncomeStatement / BalanceSheet / CashFlowStatement.

Holds raw line items as reported by the source. Derived ratios (margins, ROE,
debt ratio, free cash flow, growth rates, turnover days, etc.) live on
``FinancialMetrics`` and are computed/picked once per ``FinancialReport``.

Upstream feeds may not surface every line; missing values are ``None`` and
downstream callers should treat them as unknown rather than zero.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["IncomeStatement", "BalanceSheet", "CashFlowStatement"]


@dataclass(frozen=True)
class IncomeStatement:
    # Total operating revenue (sales) for the period (营业收入).
    revenue: float | None = None
    # Net profit attributable to shareholders of the parent company (归母净利润).
    net_profit: float | None = None
    # Net profit excluding non-recurring gains and losses (扣非净利润),
    # a cleaner proxy for profit from the core business.
    net_profit_deducted: float | None = None
    # Basic earnings per share = net profit / weighted average shares outstanding (每股收益).
    eps: float | None = None


@dataclass(frozen=True)
class BalanceSheet:
    # Total assets at period end (资产总额).
    total_assets: float | None = None
    # Total liabilities at period end (负债总额).
    total_liabilities: float | None = None
    # Total shareholders' equity at period end; total_assets - total_liabilities (股东权益合计).
    total_equity: float | None = None


@dataclass(frozen=True)
class CashFlowStatement:
    # Net cash flow generated from operating activities (经营活动现金流净额).
    operating_cash_flow: float | None = None
    # Capital expenditures: cash spent on purchases of long-term productive assets
    # such as PP&E and intangibles (资本开支).
    capex: float | None = None
