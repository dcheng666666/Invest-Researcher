"""Xueqiu endpoints for A-share company profile and spot quote.

Spot fields (现价, 总市值, …) are **point-in-time** quotes, not quarterly cumulative
accounting flows.
"""

from __future__ import annotations

import logging

import akshare as ak
import pandas as pd

from backend.infrastructure.akshare_client import ak_call_with_retry
from backend.infrastructure.disk_cache import (
    TTL_STOCK_INFO,
    cache_get,
    cache_set,
)
from backend.infrastructure.sources.eastmoney_a import (
    fetch_a_industry_em,
    fetch_a_latest_value_em_quote,
)

logger = logging.getLogger(__name__)


def _spot_field_missing(val) -> bool:
    if val is None:
        return True
    return isinstance(val, float) and pd.isna(val)


def _industry_missing(info: dict) -> bool:
    v = info.get("行业")
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    return str(v).strip() == ""


def _merge_industry_em_if_needed(code: str, info: dict) -> None:
    if not _industry_missing(info):
        return
    label = fetch_a_industry_em(code)
    if label:
        info["行业"] = label


def _merge_value_em_quote_if_needed(code: str, info: dict) -> None:
    """Fill 最新 / 总市值 / 总股本 from Eastmoney when Xueqiu spot is absent."""
    if not (
        _spot_field_missing(info.get("总市值"))
        or _spot_field_missing(info.get("最新"))
        or _spot_field_missing(info.get("总股本"))
    ):
        return
    extra = fetch_a_latest_value_em_quote(code)
    for key, value in extra.items():
        if not _spot_field_missing(info.get(key)):
            continue
        info[key] = value


def to_xq_symbol(symbol: str) -> str:
    """Convert 6-digit A-share code to Xueqiu symbol (SH600519 / SZ000333).

    BSE (Beijing Stock Exchange) listings are not currently supported.
    """
    s = symbol.strip().upper()
    if s.startswith(("SH", "SZ")):
        return s
    if len(s) == 6 and s.isdigit():
        if s.startswith("6"):
            return f"SH{s}"
        if s.startswith(("0", "3")):
            return f"SZ{s}"
    return f"SZ{s}"


def fetch_stock_info_a(code: str) -> dict:
    """Fetch A-share stock info from Xueqiu (basic profile + spot quote).

    Returns Eastmoney-compatible keys (最新, 总市值, 总股本, 行业) merged with
    the raw Xueqiu basic-info dictionary.
    """
    # v2: merge Eastmoney 估值分析 when spot omits 总市值 (e.g. expired Xueqiu token).
    cache_key = f"stock_info_xq3:{code}"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT: %s", cache_key)
        return cached

    xq_sym = to_xq_symbol(code)
    info: dict = {}

    try:
        df_basic = ak_call_with_retry(ak.stock_individual_basic_info_xq, symbol=xq_sym)
        if not df_basic.empty:
            raw = dict(zip(df_basic["item"], df_basic["value"]))
            info.update(raw)
            name = raw.get("org_short_name_cn")
            if name is not None and not (isinstance(name, float) and pd.isna(name)):
                info["股票简称"] = name
            ind = raw.get("affiliate_industry")
            if isinstance(ind, dict) and ind.get("ind_name"):
                info["行业"] = ind["ind_name"]
    except Exception as e:
        logger.error("Failed to fetch Xueqiu company info for %s: %s", code, e)

    try:
        df_spot = ak_call_with_retry(ak.stock_individual_spot_xq, symbol=xq_sym)
        if not df_spot.empty:
            spot = dict(zip(df_spot["item"], df_spot["value"]))
            info.update(spot)
            if spot.get("现价") is not None and not (
                isinstance(spot["现价"], float) and pd.isna(spot["现价"])
            ):
                info["最新"] = spot["现价"]
            mc = spot.get("资产净值/总市值")
            if mc is not None and not (isinstance(mc, float) and pd.isna(mc)):
                info["总市值"] = mc
            ts = spot.get("基金份额/总股本")
            if ts is not None and not (isinstance(ts, float) and pd.isna(ts)):
                info["总股本"] = ts
    except Exception as e:
        logger.error("Failed to fetch Xueqiu spot for %s: %s", code, e)

    if not info:
        info = {}

    _merge_value_em_quote_if_needed(code, info)
    _merge_industry_em_if_needed(code, info)

    if not info:
        return {}

    cache_set(cache_key, info, ttl=TTL_STOCK_INFO)
    return info
