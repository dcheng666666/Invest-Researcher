"""Baidu 股市通 HK valuation history (direct call, bypasses akshare wrapper).

The akshare 1.18.55 ``stock_hk_valuation_baidu`` ships with a
``http.client.HTTPSConnection`` call against ``gushitong.baidu.com`` that
does not follow the 302 redirect to ``finance.baidu.com``, so the response
body is empty and the JSON parse blows up. We hit the upstream JSON API
directly here while keeping the redirect handling and disk-cache semantics
of the rest of the source layer.

Coverage: ``period="全部"`` reaches back to listing date for old HK names
(e.g. 00700 → 2004-06-20 ≈ 22 years), at roughly biweekly cadence; daily
granularity only available for ``近一年`` / ``近三年``.

Each sample is a **point-in-time** valuation level (e.g. 总市值 in 亿港元), not
an accounting cumulative across fiscal quarters.
"""

from __future__ import annotations

import logging

import pandas as pd
import requests

from backend.infrastructure.disk_cache import TTL_PRICE, cache_get, cache_set

logger = logging.getLogger(__name__)


_BAIDU_OPENDATA_URL = "https://gushitong.baidu.com/opendata"
_USER_AGENT = "Mozilla/5.0"


def fetch_hk_valuation_baidu_history(
    hk_code: str,
    indicator: str = "总市值",
    period: str = "全部",
) -> pd.DataFrame:
    """Historical HK valuation series from Baidu 股市通.

    Returns columns ``date`` and ``market_cap`` (亿港元) when
    ``indicator="总市值"``. The function is generic enough to fetch other
    indicators (PE/PB/PS/PCF) by passing a different ``indicator`` value;
    in that case the second column is renamed ``value`` instead.

    Empty DataFrame on any failure, so callers can fall back gracefully.
    """
    hk_code = hk_code.zfill(5)
    cache_key = f"hk_valuation_baidu:{hk_code}:{indicator}:{period}"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT: %s", cache_key)
        return cached

    params = {
        "openapi": "1",
        "dspName": "iphone",
        "tn": "tangram",
        "client": "app",
        "query": indicator,
        "code": hk_code,
        "word": "",
        "resource_id": "51171",
        "market": "hk",
        "tag": indicator,
        "chart_select": period,
        "industry_select": "",
        "skip_industry": "1",
        "finClientType": "pc",
    }
    try:
        r = requests.get(
            _BAIDU_OPENDATA_URL,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=20,
            allow_redirects=True,
        )
        r.raise_for_status()
        data_json = r.json()
    except Exception as e:
        logger.warning("baidu HK valuation %s/%s failed for %s: %s", indicator, period, hk_code, e)
        return pd.DataFrame()

    try:
        body = data_json["Result"][0]["DisplayData"]["resultData"]["tplData"]["result"][
            "chartInfo"
        ][0]["body"]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning("baidu HK valuation parse failed for %s (%s/%s): %s", hk_code, indicator, period, e)
        return pd.DataFrame()

    df = pd.DataFrame(body)
    if df.empty or df.shape[1] < 2:
        return pd.DataFrame()
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)
    if df.empty:
        return df

    if indicator == "总市值":
        # Baidu publishes 总市值 in 亿港元 already, which matches the
        # ``date``/``market_cap`` (亿) shape consumed downstream — just
        # rename for consistency.
        out = df.rename(columns={"value": "market_cap"})
    else:
        out = df

    cache_set(cache_key, out, ttl=TTL_PRICE)
    return out
