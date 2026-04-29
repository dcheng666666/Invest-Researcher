"""Eastmoney HK F10 endpoints: financial main indicator, cash flow, dividend, security profile.

Upstream **flow** semantics (see also ``hk_f10_income_deaccum``):

- **Main indicator** (``RPT_HKF10_FN_MAININDICATOR``): ``OPERATE_INCOME`` and
  ``HOLDER_PROFIT`` are **fiscal year-to-date cumulants** on interim rows; they are
  converted to discrete quarters before ``FinancialReport`` construction.
- **Cash flow** (``stock_financial_hk_report_em``): ``AMOUNT`` for OCF / capex lines
  follows the same **fiscal YTD cumulative** convention; OCF and capex are passed
  through the same fiscal deaccum when every value in a fiscal block is present;
  sparse capex blocks keep raw YTD (see ``deaccumulate_hk_ytd_scalars_aligned``).
- **Dividends / prices / core indicators**: event or point-in-time series — not
  quarterly flow-statement cumulants.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Literal

import akshare as ak
import pandas as pd
import requests

from backend.infrastructure.akshare_client import ak_call_with_retry
from backend.infrastructure.disk_cache import (
    TTL_FINANCIAL,
    TTL_PRICE,
    TTL_STOCK_INFO,
    cache_get,
    cache_set,
    cached_call,
)
from backend.domain.financials.accounting import (
    AccountingContext,
    PeriodPresentation,
    ReportingStandard,
)
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
    hk_float,
    hk_period_label_from_report_date,
    hk_ratio_from_pct_field,
    hk_yoy_ratio,
    normalize_hk_indicator_df,
    report_period_from_value,
    rolling_window_cutoff,
)
from backend.infrastructure.sources._mcap_base import restrict_and_resample_mcap
from backend.infrastructure.sources.baidu_hk import fetch_hk_valuation_baidu_history
from backend.infrastructure.sources.hk_f10_income_deaccum import (
    deaccumulate_hk_main_indicator_income_rows,
    deaccumulate_hk_ytd_scalars_aligned,
)

_HK_ACCOUNTING = AccountingContext(
    currency="HKD",
    standard=ReportingStandard.IFRS,
    # Income + cash-flow lines are normalised from Eastmoney fiscal-YTD cumulants
    # to discrete quarters in ``fetch_reports_hk`` (see ``hk_f10_income_deaccum``).
    period_presentation=PeriodPresentation.DISCRETE,
)

logger = logging.getLogger(__name__)


HKIndicatorMode = Literal["报告期", "年度"]


def fetch_hk_f10_main_indicator_paginated(
    hk_code: str, indicator_mode: HKIndicatorMode
) -> pd.DataFrame:
    """Paginate Eastmoney HK F10 main-indicator API (AKShare uses pageSize=9)."""
    hk_code = hk_code.zfill(5)
    cache_key = f"hk_f10_main_indicator:{hk_code}:{indicator_mode}"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT: %s", cache_key)
        return cached

    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    sec = f"{hk_code}.HK"
    if indicator_mode == "年度":
        filter = f'(SECUCODE="{sec}")(DATE_TYPE_CODE="001")'
    else:
        filter = f'(SECUCODE="{sec}")'
    page = 1
    page_size = 200
    parts: list[pd.DataFrame] = []
    while page <= 30:
        params = {
            "reportName": "RPT_HKF10_FN_MAININDICATOR",
            "columns": "HKF10_FN_MAININDICATOR",
            "quoteColumns": "",
            "pageNumber": str(page),
            "pageSize": str(page_size),
            "sortTypes": "-1",
            "sortColumns": "STD_REPORT_DATE",
            "source": "F10",
            "client": "PC",
            "v": "01975982096513973",
            "filter": filter,
        }
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data_json = r.json()
        except Exception as e:
            logger.error("HK F10 main indicator page %d failed for %s: %s", page, hk_code, e)
            break
        result = data_json.get("result") or {}
        rows = result.get("data") or []
        if not rows:
            break
        chunk = pd.DataFrame(rows)
        chunk = normalize_hk_indicator_df(chunk)
        if chunk.empty:
            break
        parts.append(chunk)
        if len(rows) < page_size:
            break
        page += 1
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    if "REPORT_DATE" in out.columns:
        out["_rd"] = pd.to_datetime(out["REPORT_DATE"], errors="coerce")
        out = out.sort_values("_rd").drop(columns=["_rd"])
    out = out.reset_index(drop=True)
    if not out.empty:
        cache_set(cache_key, out, ttl=TTL_FINANCIAL)
    return out


def hk_latest_shares_and_mcap(hk_code: str) -> tuple[float | None, float | None]:
    """Return (issued shares, total market cap HKD) from HK core indicators snapshot."""
    hk_code = hk_code.zfill(5)
    cache_key = f"hk_core_indicator:{hk_code}"
    try:
        df = cached_call(
            cache_key, TTL_STOCK_INFO,
            ak.stock_hk_financial_indicator_em, symbol=hk_code,
        )
    except Exception as e:
        logger.error("stock_hk_financial_indicator_em failed for %s: %s", hk_code, e)
        return None, None
    if df is None or df.empty:
        return None, None
    row = df.iloc[0]
    shares = hk_float(row.get("已发行股本(股)"))
    mcap = hk_float(row.get("总市值(港元)")) or hk_float(row.get("港股市值(港元)"))
    return shares, mcap


def fetch_stock_info_hk(hk_code: str) -> dict:
    """Aggregate HK security profile, company industry, current price and shares.

    Cached at the aggregate level (``TTL_STOCK_INFO``) to avoid re-issuing all
    four downstream HTTP calls when the combined dict is requested repeatedly.
    """
    hk_code = hk_code.zfill(5)
    cache_key = f"stock_info_hk:{hk_code}"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT: %s", cache_key)
        return cached

    info: dict = {}
    try:
        prof = ak_call_with_retry(ak.stock_hk_security_profile_em, symbol=hk_code)
        if prof is not None and not prof.empty:
            r = prof.iloc[0]
            name = r.get("证券简称")
            if name is not None and not (isinstance(name, float) and pd.isna(name)):
                info["股票简称"] = str(name).strip()
    except Exception as e:
        logger.warning("stock_hk_security_profile_em failed for %s: %s", hk_code, e)

    try:
        comp = ak_call_with_retry(ak.stock_hk_company_profile_em, symbol=hk_code)
        if comp is not None and not comp.empty:
            row = comp.iloc[0]
            ind = row.get("所属行业")
            if ind is not None and not (isinstance(ind, float) and pd.isna(ind)):
                info["行业"] = str(ind).strip()
    except Exception as e:
        logger.warning("stock_hk_company_profile_em failed for %s: %s", hk_code, e)

    shares, mcap = hk_latest_shares_and_mcap(hk_code)
    if shares is not None and shares > 0:
        info["总股本"] = shares
    if mcap is not None and mcap > 0:
        info["总市值"] = mcap

    if shares and mcap and shares > 0:
        info["最新"] = mcap / shares
    else:
        try:
            hist = ak_call_with_retry(
                ak.stock_hk_hist,
                symbol=hk_code,
                period="daily",
                start_date="20200101",
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="",
            )
            if hist is not None and not hist.empty and "收盘" in hist.columns:
                last = float(hist["收盘"].iloc[-1])
                if last > 0:
                    info["最新"] = last
        except Exception as e:
            logger.warning("HK spot price fallback failed for %s: %s", hk_code, e)

    if info:
        cache_set(cache_key, info, ttl=TTL_STOCK_INFO)
    return info


def fetch_reports_hk(
    hk_code: str, window_years: int = DEFAULT_WINDOW_YEARS
) -> list[FinancialReport]:
    """Build per-period ``FinancialReport`` records for an HK stock.

    Combines the F10 main-indicator pages (revenue, profit, margins, ROE,
    debt ratio, YoY growth) with the dedicated cash-flow endpoint. Returns a
    chronologically ascending list (one report per quarter).

    ``OPERATE_INCOME`` and ``HOLDER_PROFIT`` are fiscal YTD cumulants on the
    feed; they are converted to discrete quarterly flows before building
    ``IncomeStatement`` so downstream TTM logic stays correct.
    """
    hk_code = hk_code.zfill(5)
    symbol = Symbol(code=hk_code, market=Market.HK)
    cutoff = rolling_window_cutoff(window_years)
    df = fetch_hk_f10_main_indicator_paginated(hk_code, "报告期")
    if df.empty:
        df = fetch_hk_f10_main_indicator_paginated(hk_code, "年度")
    if df.empty or "REPORT_DATE" not in df.columns:
        return []

    df = df.copy()
    df["_ts"] = pd.to_datetime(df["REPORT_DATE"], errors="coerce")
    df = df.dropna(subset=["_ts"])
    df = df[df["_ts"] >= cutoff]
    if df.empty:
        return []

    df = df.sort_values("_ts").drop_duplicates(subset=["_ts"], keep="last")

    staged: list[tuple[pd.Series, ReportPeriod, date, float | None, float | None]] = []
    for _, row in df.iterrows():
        period = report_period_from_value(row["REPORT_DATE"])
        if period is None:
            continue
        ts = row["_ts"]
        period_end = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
        staged.append(
            (
                row,
                period,
                period_end,
                hk_float(row.get("OPERATE_INCOME")),
                hk_float(row.get("HOLDER_PROFIT")),
            )
        )

    income_rows = [(d, rev, pr) for _, _, d, rev, pr in staged]
    discrete_income, fy_end_month = deaccumulate_hk_main_indicator_income_rows(
        income_rows
    )

    cash_flow_map = fetch_cash_flow_hk(hk_code, window_years)
    ocf_ytd: list[float | None] = []
    capex_ytd: list[float | None] = []
    for _, period, _, _, _ in staged:
        cf = cash_flow_map.get(period.label, {})
        ocf_ytd.append(cf.get("ocf"))
        capex_ytd.append(cf.get("capex"))
    ocf_discrete = deaccumulate_hk_ytd_scalars_aligned(
        income_rows, fy_end_month, ocf_ytd, field_name="HK_OCF"
    )
    capex_discrete = deaccumulate_hk_ytd_scalars_aligned(
        income_rows, fy_end_month, capex_ytd, field_name="HK_CAPEX"
    )

    reports: list[FinancialReport] = []
    for row_idx, (row, period, _, _, _) in enumerate(staged):
        rev_d, pr_d = discrete_income[row_idx]
        income = IncomeStatement(
            revenue=rev_d,
            net_profit=pr_d,
            net_profit_deducted=pr_d,
            # BASIC_EPS semantics are feed-defined (not re-scaled from discrete NP).
            eps=hk_float(row.get("BASIC_EPS")),
        )
        balance = BalanceSheet()
        cashflow = CashFlowStatement(
            operating_cash_flow=ocf_discrete[row_idx],
            capex=capex_discrete[row_idx],
        )
        upstream = FinancialMetrics(
            gross_margin=hk_ratio_from_pct_field(row.get("GROSS_PROFIT_RATIO")),
            net_margin=hk_ratio_from_pct_field(row.get("NET_PROFIT_RATIO")),
            roe=hk_ratio_from_pct_field(row.get("ROE_AVG")),
            # Eastmoney F10 main indicator publishes ROA directly. The HK feed
            # does not surface absolute total assets here, so unlike A-share we
            # cannot also fill BalanceSheet.total_assets — ROA stays upstream-only.
            roa=hk_ratio_from_pct_field(row.get("ROA")),
            debt_ratio=hk_ratio_from_pct_field(row.get("DEBT_ASSET_RATIO")),
            # ``CURRENT_RATIO`` is a plain multiple (e.g. ``1.32``), not a
            # percent field — use ``hk_float`` rather than the pct helper.
            # ``quick_ratio`` and ``cash_ratio`` are not exposed by the HK
            # F10 main indicator endpoint, so they stay None.
            current_ratio=hk_float(row.get("CURRENT_RATIO")),
            revenue_growth=hk_yoy_ratio(row.get("OPERATE_INCOME_YOY")),
            profit_growth=hk_yoy_ratio(row.get("HOLDER_PROFIT_YOY")),
        )
        metrics = FinancialMetrics.derive(income, balance, cashflow, upstream=upstream)
        reports.append(
            FinancialReport(
                security_id=symbol,
                period=period,
                accounting=_HK_ACCOUNTING,
                income_statement=income,
                balance_sheet=balance,
                cash_flow_statement=cashflow,
                metrics=metrics,
            )
        )
    return reports


def fetch_cash_flow_hk(
    hk_code: str, window_years: int = DEFAULT_WINDOW_YEARS
) -> dict[str, dict[str, float | None]]:
    """Fetch HK cash flow and return per-period OCF/CAPEX/FCF.

    Returns ``{period_label: {"ocf": ..., "capex": ..., "fcf": ...}}``.
    The raw ``AMOUNT`` values are **fiscal year-to-date cumulants**; ``fetch_reports_hk``
    converts them to discrete quarters together with income (see module docstring).
    """
    hk_code = hk_code.zfill(5)
    cache_key = f"cash_flow_hk:{hk_code}:{window_years}"
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT: %s", cache_key)
        return cached

    try:
        df = ak_call_with_retry(
            ak.stock_financial_hk_report_em,
            stock=hk_code,
            symbol="现金流量表",
            indicator="报告期",
        )
    except Exception as e:
        logger.error("Failed to fetch HK cash flow for %s: %s", hk_code, e)
        return {}

    if df.empty:
        return {}

    cutoff = rolling_window_cutoff(window_years)
    df = df[df["STD_ITEM_CODE"].isin(["003999", "005007"])].copy()
    df["_ts"] = pd.to_datetime(df["REPORT_DATE"], errors="coerce")
    df = df.dropna(subset=["_ts"])
    df = df[df["_ts"] >= cutoff]
    if df.empty:
        return {}

    df["_period"] = df["REPORT_DATE"].apply(hk_period_label_from_report_date)

    result: dict[str, dict[str, float | None]] = {}
    for _, row in df.iterrows():
        period = str(row["_period"])
        if period not in result:
            result[period] = {"ocf": None, "capex": None, "fcf": None}
        amount = hk_float(row.get("AMOUNT"))
        item_code = row["STD_ITEM_CODE"]
        if item_code == "003999":
            result[period]["ocf"] = amount
        elif item_code == "005007":
            result[period]["capex"] = amount

    for period, vals in result.items():
        if vals["ocf"] is not None and vals["capex"] is not None:
            vals["fcf"] = vals["ocf"] - vals["capex"]

    cache_set(cache_key, result, ttl=TTL_FINANCIAL)
    return result


def fetch_dividend_history_hk(hk_code: str) -> pd.DataFrame:
    """Fetch HK stock dividend history from Eastmoney."""
    hk_code = hk_code.zfill(5)
    cache_key = f"dividend_history_hk:{hk_code}"
    try:
        df = cached_call(
            cache_key, TTL_FINANCIAL,
            ak.stock_hk_dividend_payout_em, symbol=hk_code,
        )
    except Exception as e:
        logger.error("Failed to fetch HK dividend history for %s: %s", hk_code, e)
        return pd.DataFrame()
    return df if not df.empty else pd.DataFrame()


def fetch_price_history_hk(
    hk_code: str,
    start_date: str,
    end_date: str,
    period: str = "monthly",
) -> pd.DataFrame:
    """Fetch HK monthly/daily price history."""
    cache_key = f"price_history:{period}:HK:{hk_code}:{start_date}:{end_date}"
    try:
        return cached_call(
            cache_key, TTL_PRICE,
            ak.stock_hk_hist,
            symbol=hk_code.zfill(5),
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
    except Exception as e:
        logger.error("Failed to fetch HK price history for %s: %s", hk_code, e)
        return pd.DataFrame()


def load_hk_market_cap_frame(
    hk_code: str, window_years: int, period: str = "monthly"
) -> pd.DataFrame:
    """Monthly HK market-cap frame from Baidu 股市通 历史总市值.

    Returns columns ``date`` and ``market_cap`` (亿港元), or an empty
    DataFrame when the upstream call fails or yields no data inside the
    rolling window. Baidu publishes the actual point-in-time total market
    cap, which is the only correct historical signal here — reconstructing
    cap from daily price and the *latest* share count silently misstates
    history whenever shares outstanding changed (placements, scrip
    dividends, splits), so we deliberately do not fall back to that path.
    """
    primary = fetch_hk_valuation_baidu_history(
        hk_code, indicator="总市值", period="全部"
    )
    return restrict_and_resample_mcap(primary, window_years, period)
