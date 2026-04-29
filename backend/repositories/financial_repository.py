"""Assemble ``FinancialHistory`` aggregates from raw upstream sources.

HK paths use ``eastmoney_hk.fetch_reports_hk`` (fiscal-YTD feeds normalised to
discrete quarters at ingest). A-share paths use THS endpoints tagged
``YTD_CUMULATIVE`` for abstract + cash flow (calendar-year YTD cumulants).
"""

from __future__ import annotations

import logging
import math

from backend.domain.financials.accounting import (
    AccountingContext,
    PeriodPresentation,
    ReportingStandard,
)
from backend.domain.financials.history import FinancialHistory
from backend.domain.financials.metrics import FinancialMetrics
from backend.domain.financials.period import ReportPeriod
from backend.domain.financials.report import FinancialReport
from backend.domain.financials.statements import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
)
from backend.domain.stocks.market import Market
from backend.domain.stocks.symbol import Symbol
from backend.infrastructure.parsers import (
    DEFAULT_WINDOW_YEARS,
    parse_cn_number,
    parse_pct,
    report_period_from_value,
)
from backend.infrastructure.sources import eastmoney_hk, ths_a_share
from backend.infrastructure.symbol_resolver import parse_symbol

logger = logging.getLogger(__name__)

_A_SHARE_ACCOUNTING = AccountingContext(
    currency="CNY",
    standard=ReportingStandard.CAS,
    period_presentation=PeriodPresentation.YTD_CUMULATIVE,
)


def _eps_or_none(val) -> float | None:
    if val is None or val is False:
        return None
    s = str(val).strip()
    if s in ("", "False", "nan", "NaN"):
        return None
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _float_or_none(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        f = float(val)
    except (ValueError, TypeError):
        return None
    if math.isnan(f):
        return None
    return f


def _build_a_share_reports(
    code: str, window_years: int
) -> list[FinancialReport]:
    abstract = ths_a_share.fetch_financial_abstract(code, window_years=window_years)
    indicator = ths_a_share.fetch_financial_indicator(code, window_years=window_years)
    cash_flow = ths_a_share.fetch_cash_flow(code, window_years=window_years)

    if abstract.empty:
        return []

    symbol = Symbol(code=code, market=Market.A)

    income_by_period: dict[ReportPeriod, IncomeStatement] = {}
    upstream_by_period: dict[ReportPeriod, FinancialMetrics] = {}
    for _, row in abstract.iterrows():
        period = report_period_from_value(row["报告期"])
        if period is None:
            continue
        income_by_period[period] = IncomeStatement(
            revenue=parse_cn_number(row.get("营业总收入")),
            net_profit=parse_cn_number(row.get("净利润")),
            net_profit_deducted=parse_cn_number(row.get("扣非净利润")),
            eps=_eps_or_none(row.get("基本每股收益")),
        )
        upstream_by_period[period] = FinancialMetrics(
            gross_margin=parse_pct(row.get("销售毛利率")),
            net_margin=parse_pct(row.get("销售净利率")),
            roe=parse_pct(row.get("净资产收益率")),
            revenue_growth=parse_pct(row.get("营业总收入同比增长率")),
            profit_growth=parse_pct(row.get("扣非净利润同比增长率")),
            debt_ratio=parse_pct(row.get("资产负债率")),
            # ``流动比率`` / ``速动比率`` come as plain decimal multiples in the
            # THS abstract (e.g. 6.62 means 6.62x), so they go through
            # ``_float_or_none`` rather than ``parse_pct``.
            current_ratio=_float_or_none(row.get("流动比率")),
            quick_ratio=_float_or_none(row.get("速动比率")),
        )

    indicator_by_period: dict[ReportPeriod, dict[str, float | None]] = {}
    if not indicator.empty:
        for _, row in indicator.iterrows():
            period = report_period_from_value(row["日期"])
            if period is None or period not in income_by_period:
                continue
            # 总资产净利润率 in the THS indicator is reported as a plain percent
            # number (e.g. ``31.2554`` for 31.26%); divide by 100 to get a decimal.
            roa_raw = _float_or_none(row.get("总资产净利润率(%)"))
            cash_ratio_raw = _float_or_none(row.get("现金比率(%)"))
            indicator_by_period[period] = {
                "selling_expense_ratio": parse_pct(row.get("三项费用比重")),
                "receivable_turnover_days": _float_or_none(
                    row.get("应收账款周转天数(天)")
                ),
                "inventory_turnover_days": _float_or_none(
                    row.get("存货周转天数(天)")
                ),
                "total_assets": _float_or_none(row.get("总资产(元)")),
                "roa": roa_raw / 100.0 if roa_raw is not None else None,
                # 现金比率 is reported as a plain percent (e.g. ``145.6`` =
                # 145.6%); store as a decimal to match the rest of the
                # ``cash_ratio`` field's contract.
                "cash_ratio": (
                    cash_ratio_raw / 100.0 if cash_ratio_raw is not None else None
                ),
            }

    cashflow_by_period: dict[ReportPeriod, CashFlowStatement] = {}
    if not cash_flow.empty:
        for _, row in cash_flow.iterrows():
            period = report_period_from_value(row["报告期"])
            if period is None or period not in income_by_period:
                continue
            cashflow_by_period[period] = CashFlowStatement(
                operating_cash_flow=parse_cn_number(
                    row.get("*经营活动产生的现金流量净额")
                ),
                capex=parse_cn_number(
                    row.get("购建固定资产、无形资产和其他长期资产支付的现金")
                ),
            )

    reports: list[FinancialReport] = []
    for period, income in income_by_period.items():
        cashflow = cashflow_by_period.get(period, CashFlowStatement())
        ind = indicator_by_period.get(period, {})
        upstream = upstream_by_period[period]
        # THS does not publish absolute total liabilities / equity in either the
        # abstract or the indicator endpoint, but it gives total_assets plus the
        # debt-to-asset ratio, so liabilities and equity can be back-derived
        # exactly: TL = TA * dr, TE = TA - TL.
        total_assets = ind.get("total_assets")
        debt_ratio = upstream.debt_ratio
        if total_assets is not None and debt_ratio is not None:
            total_liabilities = total_assets * debt_ratio
            total_equity = total_assets - total_liabilities
        else:
            total_liabilities = None
            total_equity = None
        balance = BalanceSheet(
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
        )
        upstream = FinancialMetrics(
            gross_margin=upstream.gross_margin,
            net_margin=upstream.net_margin,
            roe=upstream.roe,
            roa=ind.get("roa"),
            debt_ratio=upstream.debt_ratio,
            current_ratio=upstream.current_ratio,
            quick_ratio=upstream.quick_ratio,
            cash_ratio=ind.get("cash_ratio"),
            revenue_growth=upstream.revenue_growth,
            profit_growth=upstream.profit_growth,
            receivable_turnover_days=ind.get("receivable_turnover_days"),
            inventory_turnover_days=ind.get("inventory_turnover_days"),
            selling_expense_ratio=ind.get("selling_expense_ratio"),
        )
        metrics = FinancialMetrics.derive(income, balance, cashflow, upstream=upstream)
        reports.append(
            FinancialReport(
                security_id=symbol,
                period=period,
                accounting=_A_SHARE_ACCOUNTING,
                income_statement=income,
                balance_sheet=balance,
                cash_flow_statement=cashflow,
                metrics=metrics,
            )
        )
    return reports


def get_financial_history(
    symbol: str, window_years: int = DEFAULT_WINDOW_YEARS
) -> FinancialHistory:
    """Build a ``FinancialHistory`` aggregate for the requested stock."""
    canonical = parse_symbol(symbol)
    if canonical.market is Market.HK:
        reports = eastmoney_hk.fetch_reports_hk(canonical.code, window_years=window_years)
    else:
        reports = _build_a_share_reports(canonical.code, window_years)
    return FinancialHistory.of(canonical, reports)
