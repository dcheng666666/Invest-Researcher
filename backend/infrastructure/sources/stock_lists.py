"""Fetch full A-share and HK stock code/name lists (used by symbol sync script).

These endpoints return **reference / listing** metadata (code, name), not
quarterly income-statement cumulants.
"""

from __future__ import annotations

import logging

import akshare as ak
import pandas as pd

from backend.infrastructure.akshare_client import ak_call_with_retry
from backend.infrastructure.disk_cache import (
    TTL_FINANCIAL,
    cache_get,
    cache_set,
)

logger = logging.getLogger(__name__)


def a_share_market_for_code(code: str) -> str:
    """Infer exchange bucket from A-share code (used as DB primary-key partition).

    BSE (Beijing Stock Exchange) listings (codes starting with 8/4) are not
    currently supported and bucketed as ``OTHER`` so callers can filter them out.
    """
    c = str(code).strip()
    if c.startswith("6"):
        return "SH"
    if c.startswith(("0", "3")):
        return "SZ"
    return "OTHER"


def _normalize_a_code_name_df(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["code", "name"])
    df = raw.copy()
    if "code" in df.columns and "name" in df.columns:
        out = df[["code", "name"]]
    elif "代码" in df.columns and "名称" in df.columns:
        out = df.rename(columns={"代码": "code", "名称": "name"})[["code", "name"]]
    else:
        logger.warning("A-share DataFrame missing code/name columns: %s", list(df.columns))
        return pd.DataFrame(columns=["code", "name"])
    out = out.copy()
    out["code"] = out["code"].astype(str).str.strip()
    out["name"] = out["name"].astype(str).str.strip()
    return out


def fetch_a_share_code_name_df() -> pd.DataFrame:
    cache_key = "a_share_code_name_list"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT: %s", cache_key)
        return cached
    try:
        raw = ak.stock_info_a_code_name()
        result = _normalize_a_code_name_df(raw)
    except Exception:
        logger.warning("stock_info_a_code_name failed, falling back to SH+SZ only")
        frames: list[pd.DataFrame] = []
        for func in (ak.stock_info_sh_name_code, ak.stock_info_sz_name_code):
            try:
                df = func(indicator="A股")
                if "证券代码" in df.columns:
                    df = df.rename(columns={"证券代码": "code", "证券简称": "name"})
                elif "A股代码" in df.columns:
                    df = df.rename(columns={"A股代码": "code", "A股简称": "name"})
                frames.append(df[["code", "name"]])
            except Exception as e:
                logger.warning("Fallback fetch failed: %s", e)
        if not frames:
            return pd.DataFrame(columns=["code", "name"])
        merged = pd.concat(frames, ignore_index=True)
        result = _normalize_a_code_name_df(merged)
    if not result.empty:
        cache_set(cache_key, result, ttl=TTL_FINANCIAL)
    return result


def normalize_hk_spot_df(raw: pd.DataFrame) -> pd.DataFrame | None:
    if raw is None or raw.empty:
        return None
    if "代码" in raw.columns and "名称" in raw.columns:
        out = raw[["代码", "名称"]].rename(columns={"代码": "code", "名称": "name"})
    elif "代码" in raw.columns and "中文名称" in raw.columns:
        out = raw[["代码", "中文名称"]].rename(columns={"代码": "code", "中文名称": "name"})
    else:
        logger.warning("HK spot DataFrame missing expected columns: %s", list(raw.columns))
        return None
    out = out.copy()
    out["code"] = out["code"].astype(str).str.replace(r"\.HK$", "", regex=True).str.zfill(5)
    out["name"] = out["name"].astype(str).str.strip()
    return out


def load_hk_list_from_sources() -> pd.DataFrame | None:
    """Eastmoney first; then Sina with retries if EM is blocked."""
    for label, func, use_retry in (
        ("stock_hk_spot_em", ak.stock_hk_spot_em, False),
        ("stock_hk_main_board_spot_em", ak.stock_hk_main_board_spot_em, False),
        ("stock_hk_spot (sina)", ak.stock_hk_spot, True),
    ):
        try:
            raw = ak_call_with_retry(func) if use_retry else func()
            norm = normalize_hk_spot_df(raw)
            if norm is not None and not norm.empty:
                logger.info("HK stock list loaded via %s (%d rows)", label, len(norm))
                return norm
        except Exception as e:
            logger.warning("%s failed: %s", label, e)
    return None


def fetch_hk_stock_list_df() -> pd.DataFrame:
    cache_key = "hk_stock_list"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT: %s", cache_key)
        return cached
    hk = load_hk_list_from_sources()
    if hk is not None and not hk.empty:
        cache_set(cache_key, hk, ttl=TTL_FINANCIAL)
        return hk
    logger.warning("All HK list sources failed")
    return pd.DataFrame(columns=["code", "name"])
