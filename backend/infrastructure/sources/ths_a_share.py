"""THS (同花顺) endpoints for A-share financial abstracts, indicators, cash flow, dividends.

Quarterly ``按报告期`` abstracts and cash-flow tables follow **CAS-style calendar
year-to-date cumulants** within each calendar year (Q1 = first quarter, Q2 = H1,
etc.). The repository tags these rows with ``PeriodPresentation.YTD_CUMULATIVE``.
"""

from __future__ import annotations

import logging

import akshare as ak
import pandas as pd

from backend.infrastructure.disk_cache import TTL_FINANCIAL, cached_call
from backend.infrastructure.parsers import (
    DEFAULT_WINDOW_YEARS,
    report_on_or_after_cutoff,
    rolling_window_cutoff,
)

logger = logging.getLogger(__name__)

# THS ``进度`` values we keep for cash-dividend history. ``预案`` is included
# so pending board proposals appear before ex-date; when the same scheme
# later reaches ``实施``, ``_drop_superseded_proposals`` removes the earlier
# 预案 to avoid double-counting.
_A_SHARE_DIVIDEND_PROGRESS = frozenset({"实施", "预案"})


def _payout_per_10_compare_key(raw: object) -> float | None:
    """Normalise ``派息`` (per 10 shares) for matching 预案 to later 实施."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if pd.isna(v):
        return None
    return round(v, 6)


def _drop_superseded_proposals(df: pd.DataFrame) -> pd.DataFrame:
    """Drop 预案 rows when a later 实施 row has the same per-10 派息 amount."""
    if df.empty or "进度" not in df.columns:
        return df
    work = df.copy()
    work["_announce_ts"] = pd.to_datetime(work["公告日期"], errors="coerce")
    work = work.sort_values("_announce_ts", ascending=True, na_position="first")
    work = work.reset_index(drop=True)
    drop_positions: list[int] = []
    n = len(work)
    for i in range(n):
        if work.iloc[i]["进度"] != "预案":
            continue
        pay_i = _payout_per_10_compare_key(work.iloc[i]["派息"])
        if pay_i is None:
            continue
        for j in range(i + 1, n):
            if work.iloc[j]["进度"] != "实施":
                continue
            if _payout_per_10_compare_key(work.iloc[j]["派息"]) == pay_i:
                drop_positions.append(i)
                break
    out = work.drop(index=drop_positions).drop(columns=["_announce_ts"])
    return out.reset_index(drop=True)


def fetch_financial_abstract(
    code: str, window_years: int = DEFAULT_WINDOW_YEARS
) -> pd.DataFrame:
    """Fetch quarterly financial abstract from THS (A-share only)."""
    cache_key = f"financial_abstract:{code}:{window_years}"
    try:
        df = cached_call(
            cache_key, TTL_FINANCIAL,
            ak.stock_financial_abstract_ths, symbol=code, indicator="按报告期",
        )
    except Exception as e:
        logger.error("Failed to fetch financial abstract for %s: %s", code, e)
        return pd.DataFrame()

    if df.empty:
        return df

    df = df.sort_values("报告期").reset_index(drop=True)
    cutoff = rolling_window_cutoff(window_years)
    df = df[df["报告期"].apply(lambda x: report_on_or_after_cutoff(x, cutoff))]
    return df.reset_index(drop=True)


def fetch_financial_indicator(
    code: str,
    start_year: str | None = None,
    window_years: int = DEFAULT_WINDOW_YEARS,
) -> pd.DataFrame:
    """Fetch detailed financial analysis indicators (all report periods)."""
    cutoff = rolling_window_cutoff(window_years)
    if start_year is None:
        start_year = str(cutoff.year)
    cache_key = f"financial_indicator:{code}:{start_year}"
    try:
        df = cached_call(
            cache_key, TTL_FINANCIAL,
            ak.stock_financial_analysis_indicator, symbol=code, start_year=start_year,
        )
    except Exception as e:
        logger.error("Failed to fetch financial indicator for %s: %s", code, e)
        return pd.DataFrame()

    if df.empty:
        return df

    df["日期"] = pd.to_datetime(df["日期"])
    df = df[df["日期"] >= cutoff]
    df = df.sort_values("日期").reset_index(drop=True)
    return df


def fetch_cash_flow(
    code: str, window_years: int = DEFAULT_WINDOW_YEARS
) -> pd.DataFrame:
    """Fetch quarterly cash flow statements from THS."""
    cache_key = f"cash_flow:{code}:{window_years}"
    try:
        df = cached_call(
            cache_key, TTL_FINANCIAL,
            ak.stock_financial_cash_ths, symbol=code, indicator="按报告期",
        )
    except Exception as e:
        logger.error("Failed to fetch cash flow for %s: %s", code, e)
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.sort_values("报告期").reset_index(drop=True)
    cutoff = rolling_window_cutoff(window_years)
    df = df[df["报告期"].apply(lambda x: report_on_or_after_cutoff(x, cutoff))]
    return df


def fetch_dividend_history(code: str) -> tuple[pd.DataFrame, bool]:
    """Fetch A-share dividend history.

    Returns ``(dataframe, has_no_distribution)`` where ``has_no_distribution``
    is True when the API returned records but all entries are "不分配" (the
    company explicitly chose not to pay dividends).

    Rows with ``进度`` in ``{"实施", "预案"}`` are kept. A 预案 row is removed
    when a later ``实施`` row has the same ``派息`` (per 10 shares) so the
    same scheme is not double-counted. Other ``进度`` values are excluded.
    """
    cache_key = f"dividend_history:v2:{code}"
    try:
        df = cached_call(
            cache_key, TTL_FINANCIAL,
            ak.stock_history_dividend_detail, symbol=code, indicator="分红",
        )
    except Exception as e:
        logger.error("Failed to fetch dividend history for %s: %s", code, e)
        return pd.DataFrame(), False
    if df.empty:
        return df, False
    has_no_distribution = bool(
        "进度" in df.columns
        and (df["进度"] == "不分配").all()
    )
    if "进度" not in df.columns:
        return pd.DataFrame(), has_no_distribution
    df = df[df["进度"].isin(_A_SHARE_DIVIDEND_PROGRESS)].copy()
    df = _drop_superseded_proposals(df)
    df = df.sort_values("公告日期").reset_index(drop=True)
    return df, has_no_distribution
