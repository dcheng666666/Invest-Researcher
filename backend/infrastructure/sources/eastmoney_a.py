"""Eastmoney A-share endpoints: daily K-line and 估值分析 (market-cap history).

This module is the A-share counterpart to ``eastmoney_hk.py`` — it owns
both the price-history loader (``fetch_price_history_a``) and the
market-cap loader (``load_a_market_cap_frame``), the latter built on top
of the 估值分析 endpoint which returns one row per trading day with full
valuation columns precomputed (总市值, 流通市值, 总股本, 流通股本,
PE-TTM, PE-LAR, 市净率, PEG, 市现率, 市销率). Coverage of 估值分析 starts
in 2018 for most listed names; older history is intentionally not
reconstructed from price + share-change endpoints.

``PE-TTM`` / ``市销率`` etc. on each row are **vendor-precomputed** metrics for
that trading day, not raw quarterly income-statement cumulants from this feed.
"""

from __future__ import annotations

import logging
from typing import Any

import akshare as ak
import pandas as pd

from backend.infrastructure.disk_cache import TTL_PRICE, TTL_STOCK_INFO, cached_call
from backend.infrastructure.sources._mcap_base import restrict_and_resample_mcap

logger = logging.getLogger(__name__)


def fetch_a_latest_value_em_quote(code: str) -> dict[str, Any]:
    """Latest close, market cap, and total shares from Eastmoney 估值分析.

    Used when Xueqiu spot is unavailable (e.g. expired public token) so
    ``Security`` / valuation steps still receive yuan-denominated
    ``总市值`` and share count consistent with ``stock_value_em`` history.
    """
    cache_key = f"stock_value_em:{code}"
    try:
        df = cached_call(
            cache_key, TTL_PRICE,
            ak.stock_value_em, symbol=code,
        )
    except Exception as e:
        logger.error("stock_value_em (latest quote) failed for %s: %s", code, e)
        return {}
    if df is None or df.empty:
        return {}
    required = ("当日收盘价", "总市值", "总股本")
    if not all(c in df.columns for c in required):
        return {}
    row = df.iloc[-1]
    out: dict[str, Any] = {}
    close = pd.to_numeric(row["当日收盘价"], errors="coerce")
    if not pd.isna(close):
        out["最新"] = float(close)
    mcap = pd.to_numeric(row["总市值"], errors="coerce")
    if not pd.isna(mcap):
        out["总市值"] = float(mcap)
    shares = pd.to_numeric(row["总股本"], errors="coerce")
    if not pd.isna(shares):
        out["总股本"] = float(shares)
    return out


def fetch_a_industry_em(code: str) -> str | None:
    """Industry label (行业) from Eastmoney 个股信息.

    Xueqiu company.json often omits ``affiliate_industry`` when the public
    token is rejected or the payload shape changes; this endpoint is a
    reliable secondary source for the same downstream ``行业`` key.
    """
    cache_key = f"stock_industry_em:{code}"
    try:
        df = cached_call(
            cache_key,
            TTL_STOCK_INFO,
            ak.stock_individual_info_em,
            symbol=code,
        )
    except Exception as e:
        logger.error("stock_individual_info_em (industry) failed for %s: %s", code, e)
        return None
    if df is None or df.empty:
        return None
    if "item" not in df.columns or "value" not in df.columns:
        return None
    rows = dict(zip(df["item"], df["value"]))
    raw = rows.get("行业")
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    label = str(raw).strip()
    return label if label else None


def fetch_price_history_a(
    code: str,
    start_date: str,
    end_date: str,
    period: str = "monthly",
) -> pd.DataFrame:
    """Fetch A-share monthly/daily price history (Eastmoney, 前复权)."""
    cache_key = f"price_history:{period}:A:{code}:{start_date}:{end_date}"
    try:
        return cached_call(
            cache_key, TTL_PRICE,
            ak.stock_zh_a_hist,
            symbol=code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
    except Exception as e:
        logger.error("Failed to fetch A-share price history for %s: %s", code, e)
        return pd.DataFrame()


def fetch_value_em_history(code: str) -> pd.DataFrame:
    """Daily 总市值 history (in 亿元) from Eastmoney 估值分析.

    Returns columns ``date`` and ``market_cap`` (in 亿元), matching the
    shape consumed by ``load_a_market_cap_frame``. Empty DataFrame on
    failure.
    """
    cache_key = f"stock_value_em:{code}"
    try:
        df = cached_call(
            cache_key, TTL_PRICE,
            ak.stock_value_em, symbol=code,
        )
    except Exception as e:
        logger.error("stock_value_em failed for %s: %s", code, e)
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    if "数据日期" not in df.columns or "总市值" not in df.columns:
        return pd.DataFrame()
    out = pd.DataFrame({
        "date": pd.to_datetime(df["数据日期"], errors="coerce"),
        # ``总市值`` is published in 元; downstream contract is 亿元.
        "market_cap": pd.to_numeric(df["总市值"], errors="coerce") / 1e8,
    })
    out = out.dropna(subset=["date", "market_cap"]).sort_values("date")
    return out.reset_index(drop=True)


def load_a_market_cap_frame(
    code: str, window_years: int, period: str = "monthly"
) -> pd.DataFrame:
    """Monthly A-share market-cap frame from Eastmoney 估值分析.

    Returns columns ``date`` and ``market_cap`` (亿元), or an empty
    DataFrame when the upstream call fails or yields no data inside the
    rolling window.
    """
    primary = fetch_value_em_history(code)
    return restrict_and_resample_mcap(primary, window_years, period)
