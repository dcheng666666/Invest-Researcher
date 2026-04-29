"""Raw external data-source clients organized per upstream provider.

Importers should reach into specific submodules (``ths_a_share``,
``eastmoney_hk``, ``eastmoney_a``, ``baidu_hk``, ``xueqiu``,
``stock_lists``). Repositories compose them; nothing in the domain layer
imports from here.

**Quarterly flow semantics (cumulative vs discrete on the wire)**

A-share (THS via ``financial_repository``):

- Income (``stock_financial_abstract_ths``): calendar **YTD cumulative** within
  each calendar year — ``YTD_CUMULATIVE``.
- Cash flow (``stock_financial_cash_ths``): same **YTD cumulative** convention.

HK (Eastmoney via ``eastmoney_hk.fetch_reports_hk``):

- Main indicator (``RPT_HKF10_FN_MAININDICATOR``): ``OPERATE_INCOME`` /
  ``HOLDER_PROFIT`` are **fiscal YTD** cumulants; converted to discrete quarters
  in ``hk_f10_income_deaccum`` before ``DISCRETE`` storage.
- Cash flow (``stock_financial_hk_report_em``): **fiscal YTD** cumulants; OCF /
  capex use the same fiscal deaccum when every value in a fiscal block is
  present; sparse capex may remain raw YTD (``deaccumulate_hk_ytd_scalars_aligned``).

Non-flow series:

- Eastmoney A ``stock_value_em``: daily point-in-time totals and vendor PE-TTM.
- Baidu HK valuation history: point-in-time market cap samples.
- Xueqiu spot / profile: point-in-time or static attributes.
- Dividend endpoints: corporate-action events, not income-statement quarters.
- Price history: OHLCV bars, not cumulative accounting.
"""

import pandas as pd

from backend.domain.stocks.market import Market
from backend.infrastructure.sources._mcap_base import (
    monthly_mcap_rows,
    quarterly_mcap_rows,
)
from backend.infrastructure.sources.eastmoney_a import load_a_market_cap_frame
from backend.infrastructure.sources.eastmoney_hk import load_hk_market_cap_frame


def load_market_cap_frame(
    mkt: Market, code: str, window_years: int, period: str = "monthly"
) -> pd.DataFrame:
    """Dispatch to the per-market market-cap loader.

    Returns columns ``date`` and ``market_cap`` (亿, currency follows the
    market — HKD for HK, CNY for A-share), or an empty DataFrame on
    upstream failure.
    """
    if mkt is Market.HK:
        return load_hk_market_cap_frame(code, window_years, period)
    return load_a_market_cap_frame(code, window_years, period)


__all__ = [
    "monthly_mcap_rows",
    "quarterly_mcap_rows",
    "load_market_cap_frame",
    "load_hk_market_cap_frame",
    "load_a_market_cap_frame",
]
