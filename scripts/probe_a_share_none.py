"""Probe which metric attrs are None across the FinancialHistory for a code.

Usage: uv run python scripts/probe_a_share_none.py 600519
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict

logging.basicConfig(level=logging.ERROR)

from backend.repositories.financial_repository import get_financial_history


METRIC_ATTRS = [
    "gross_margin",
    "net_margin",
    "roe",
    "roa",
    "debt_ratio",
    "current_ratio",
    "quick_ratio",
    "cash_ratio",
    "revenue_growth",
    "profit_growth",
    "receivable_turnover_days",
    "inventory_turnover_days",
    "selling_expense_ratio",
    "free_cash_flow",
]
INCOME_ATTRS = ["revenue", "net_profit", "net_profit_deducted", "eps"]
BALANCE_ATTRS = ["total_assets", "total_liabilities", "total_equity"]
CASHFLOW_ATTRS = ["operating_cash_flow", "capex"]


def main() -> None:
    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    history = get_financial_history(code)
    if not history.has_data():
        print(f"no data for {code}")
        return

    none_periods: dict[str, list[str]] = defaultdict(list)
    have_periods: dict[str, list[str]] = defaultdict(list)

    for r in history.reports:
        label = r.period.label
        for a in METRIC_ATTRS:
            v = getattr(r.metrics, a)
            (none_periods if v is None else have_periods)[a].append(label)
        for a in INCOME_ATTRS:
            v = getattr(r.income_statement, a)
            (none_periods if v is None else have_periods)[a].append(label)
        for a in BALANCE_ATTRS:
            v = getattr(r.balance_sheet, a)
            (none_periods if v is None else have_periods)[a].append(label)
        for a in CASHFLOW_ATTRS:
            v = getattr(r.cash_flow_statement, a)
            (none_periods if v is None else have_periods)[a].append(label)

    print(f"\n=== {code} reports={len(history.reports)} "
          f"range={history.reports[0].period.label}..{history.reports[-1].period.label} ===\n")
    print(f"{'attr':30s}  {'#none':>6}  {'#have':>6}  none_periods (first..last)")
    print("-" * 90)
    for a in METRIC_ATTRS + INCOME_ATTRS + BALANCE_ATTRS + CASHFLOW_ATTRS:
        nones = none_periods.get(a, [])
        haves = have_periods.get(a, [])
        if nones:
            span = f"{nones[0]}..{nones[-1]}" if len(nones) > 1 else nones[0]
        else:
            span = "-"
        print(f"{a:30s}  {len(nones):>6}  {len(haves):>6}  {span}")


if __name__ == "__main__":
    main()
