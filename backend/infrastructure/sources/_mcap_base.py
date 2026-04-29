"""Helpers shared by per-market market-cap loaders.

Both supported markets (HK, A-share) have a primary upstream that publishes
point-in-time total market cap directly (Baidu 股市通 for HK, Eastmoney
估值分析 for A-share). The helpers here (a) clip such a frame to the
requested rolling window and resample to month-end, and (b) flatten the
resulting frame into the ``(YYYY-MM, value_yi)`` pairs the repository layer
consumes.

There is intentionally no ``MktCapSource`` abstraction or fallback chain:
if the primary upstream fails, callers receive an empty frame and the
domain layer surfaces an empty ``MarketCapHistory``.
"""

from __future__ import annotations

import pandas as pd

from backend.infrastructure.parsers import rolling_window_cutoff


def restrict_and_resample_mcap(
    df: pd.DataFrame, window_years: int, period: str = "monthly"
) -> pd.DataFrame:
    """Apply window cutoff + monthly resample to a ``[date, market_cap]`` frame.

    Used by sources that already return computed market cap (e.g. Eastmoney
    估值分析 / Baidu 总市值). Output columns are ``date`` and ``market_cap``
    (亿), with one observation per calendar month when ``period="monthly"``
    (last available value within the month).
    """
    if df is None or df.empty or "date" not in df.columns or "market_cap" not in df.columns:
        return pd.DataFrame()
    out = df[["date", "market_cap"]].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["market_cap"] = pd.to_numeric(out["market_cap"], errors="coerce")
    out = out.dropna(subset=["date", "market_cap"]).sort_values("date")
    cutoff = rolling_window_cutoff(window_years)
    out = out[out["date"] >= cutoff]
    if out.empty:
        return pd.DataFrame()
    if period == "monthly":
        s = out.set_index("date")["market_cap"].resample("ME").last().dropna()
        out = s.reset_index()
    return out.reset_index(drop=True)


def monthly_mcap_rows(df: pd.DataFrame) -> list[tuple[str, float]]:
    work = df.copy()
    work["ym"] = work["date"].dt.strftime("%Y-%m")
    work = work.dropna(subset=["ym", "market_cap"]).sort_values("date")
    deduped = work.drop_duplicates(subset=["ym"], keep="last")
    return [
        (str(row["ym"]), round(float(row["market_cap"]), 2))
        for _, row in deduped.iterrows()
    ]


def quarterly_mcap_rows(df: pd.DataFrame) -> list[tuple[str, float]]:
    if df.empty:
        return []
    work = df.copy()
    work["quarter"] = (
        work["date"].dt.year.astype(str)
        + "Q"
        + work["date"].dt.quarter.astype(str)
    )
    quarterly = work.groupby("quarter")["market_cap"].mean()
    return [(q, round(float(v), 2)) for q, v in quarterly.items()]
