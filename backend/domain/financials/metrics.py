"""Per-report derived metrics value object.

``FinancialMetrics`` carries the ratios a single ``FinancialReport`` exposes:
margins, ROE, debt ratio, year-on-year growth rates, working-capital
efficiency, and free cash flow. It is *derived* from the three statements
plus optional upstream-supplied ratios — most domestic data feeds publish
margins/ROE/growth rates directly, and we adopt those when available, only
falling back to local computation for free cash flow.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.financials.statements import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
)

__all__ = ["FinancialMetrics"]


@dataclass(frozen=True)
class FinancialMetrics:
    """Per-report ratios plus free cash flow.

    Percentage-typed fields are stored as decimals (``0.2338`` means 23.38%),
    matching the output of ``parse_pct`` / ``hk_ratio_from_pct_field``. Upstream
    field-name references like ``销售毛利率`` / ``GROSS_PROFIT_RATIO`` denote the
    raw keys read from the THS A-share / Eastmoney HK feeds respectively.
    """

    gross_margin: float | None = None
    """Gross profit / revenue. A-share: ``销售毛利率``. HK: ``GROSS_PROFIT_RATIO``."""

    net_margin: float | None = None
    """Net profit / revenue. A-share: ``销售净利率``. HK: ``NET_PROFIT_RATIO``."""

    roe: float | None = None
    """Return on equity. A-share: ``净资产收益率``.
    HK: ``ROE_AVG`` (weighted average over the period)."""

    roa: float | None = None
    """Return on assets (net profit / total assets). A-share: ``总资产净利润率``
    from the THS indicator endpoint. HK: ``ROA`` from Eastmoney F10 main indicator.
    Falls back to ``net_profit / total_assets`` when both line items exist on
    the report (currently only A-share supplies a populated balance sheet)."""

    debt_ratio: float | None = None
    """Total liabilities / total assets.
    A-share: ``资产负债率``. HK: ``DEBT_ASSET_RATIO``."""

    current_ratio: float | None = None
    """Current assets / current liabilities (a multiple, NOT a percent —
    e.g. ``1.5`` means 1.5×). A-share: ``流动比率``. HK: ``CURRENT_RATIO``."""

    quick_ratio: float | None = None
    """(Current assets − inventory) / current liabilities, also a multiple.
    A-share: ``速动比率``. The HK F10 indicator does not surface this."""

    cash_ratio: float | None = None
    """Cash + cash-equivalents / current liabilities, stored as a decimal
    (``0.30`` == 30%). A-share: ``现金比率(%)`` from the indicator endpoint
    (raw percent, divided by 100 here). HK does not supply this."""

    revenue_growth: float | None = None
    """Year-on-year revenue growth.
    A-share: ``营业总收入同比增长率``. HK: ``OPERATE_INCOME_YOY``."""

    profit_growth: float | None = None
    """Year-on-year profit growth. NOTE: the underlying profit definition is
    feed-dependent and the two are NOT directly comparable:
    A-share uses non-recurring-stripped profit (``扣非净利润同比增长率``);
    HK uses profit attributable to shareholders (``HOLDER_PROFIT_YOY``)."""

    receivable_turnover_days: float | None = None
    """Days sales outstanding (unit: days). Sourced from THS A-share indicator
    ``应收账款周转天数(天)``; the HK feed does not supply this."""

    inventory_turnover_days: float | None = None
    """Days inventory outstanding (unit: days). Sourced from THS A-share
    indicator ``存货周转天数(天)``; the HK feed does not supply this."""

    selling_expense_ratio: float | None = None
    """MISNOMER kept for backward compatibility: actually THS ``三项费用比重``,
    i.e. (selling + admin + finance expenses) / revenue, not selling expense
    alone. A-share only."""

    free_cash_flow: float | None = None
    """Free cash flow in the report's reporting currency, derived locally as
    ``operating_cash_flow - capex`` when both are present (see ``derive``).
    Inherits the period accumulation convention of the source cash-flow
    statement (see ``AccountingContext.period_presentation``)."""

    @classmethod
    def derive(
        cls,
        income_statement: IncomeStatement,
        balance_sheet: BalanceSheet,
        cash_flow_statement: CashFlowStatement,
        *,
        upstream: "FinancialMetrics | None" = None,
    ) -> "FinancialMetrics":
        """Build the per-report metrics, preferring upstream ratios when given.

        Free cash flow is computed locally as ``OCF - Capex`` whenever both
        cash-flow line items are present. ROA falls back to
        ``net_profit / total_assets`` when upstream omits it but the income
        statement and balance sheet both supply the line items.
        """
        u = upstream or cls()
        ocf = cash_flow_statement.operating_cash_flow
        capex = cash_flow_statement.capex
        fcf = u.free_cash_flow
        if fcf is None and ocf is not None and capex is not None:
            fcf = ocf - capex

        roa = u.roa
        if roa is None:
            net_profit = income_statement.net_profit
            total_assets = balance_sheet.total_assets
            if net_profit is not None and total_assets and total_assets != 0:
                roa = net_profit / total_assets

        return cls(
            gross_margin=u.gross_margin,
            net_margin=u.net_margin,
            roe=u.roe,
            roa=roa,
            debt_ratio=u.debt_ratio,
            current_ratio=u.current_ratio,
            quick_ratio=u.quick_ratio,
            cash_ratio=u.cash_ratio,
            revenue_growth=u.revenue_growth,
            profit_growth=u.profit_growth,
            receivable_turnover_days=u.receivable_turnover_days,
            inventory_turnover_days=u.inventory_turnover_days,
            selling_expense_ratio=u.selling_expense_ratio,
            free_cash_flow=fcf,
        )
