"""Dividend-history retrieval, returning the ``DividendHistory`` aggregate."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from backend.domain.dividends.amounts import DividendPerShare
from backend.domain.dividends.history import DividendHistory
from backend.domain.dividends.record import DividendRecord
from backend.domain.dividends.types import DividendType
from backend.domain.stocks.market import Market
from backend.infrastructure.parsers import (
    parse_hk_dividend_per_share,
    ths_fiscal_year_from_announcement,
)
from backend.infrastructure.sources import eastmoney_hk, ths_a_share
from backend.infrastructure.symbol_resolver import parse_symbol

logger = logging.getLogger(__name__)


def get_history(symbol: str) -> DividendHistory:
    sym = parse_symbol(symbol)
    if sym.market is Market.HK:
        df = eastmoney_hk.fetch_dividend_history_hk(sym.code)
        records = _records_from_hk(df, currency=sym.market.default_currency)
        return DividendHistory.of(records=records, has_no_distribution=False)
    df, has_no_distribution = ths_a_share.fetch_dividend_history(sym.code)
    records = _records_from_a(df, currency=sym.market.default_currency)
    return DividendHistory.of(records=records, has_no_distribution=has_no_distribution)


def _records_from_a(df: pd.DataFrame, currency: str) -> list[DividendRecord]:
    """Map THS A-share dividend rows into DividendRecord value objects.

    THS exposes ``派息`` as cash distributed *per 10 shares* in CNY; we divide
    by 10 to get per-share DPS. The fiscal year is inferred from the
    announcement date because THS does not provide an explicit fiscal-year
    column. Rows with no parsable announcement date are skipped since their
    fiscal year cannot be resolved.
    """
    if df is None or df.empty:
        return []
    records: list[DividendRecord] = []
    for _, row in df.iterrows():
        payout_per_10 = _safe_float(row.get("派息"))
        if payout_per_10 is None or payout_per_10 <= 0:
            continue
        announcement = _parse_date(row.get("公告日期"))
        if announcement is None:
            continue
        records.append(
            DividendRecord(
                fiscal_year=ths_fiscal_year_from_announcement(announcement),
                dividend_per_share=DividendPerShare(
                    amount=payout_per_10 / 10.0, currency=currency
                ),
                dividend_type=DividendType.CASH,
                announcement_date=announcement,
                ex_dividend_date=_parse_date(row.get("除权除息日")),
            )
        )
    return records


def _records_from_hk(df: pd.DataFrame, currency: str) -> list[DividendRecord]:
    """Map Eastmoney HK dividend rows into DividendRecord value objects.

    HK rows ship an explicit ``财政年度`` column, so we use it verbatim. Cash
    DPS is parsed out of the free-text ``分红方案`` field; rows whose plan
    does not match a recognised cash-dividend phrase (送股 / 转增 / 特别) are
    silently skipped, matching the legacy aggregation behaviour.
    """
    if df is None or df.empty:
        return []
    records: list[DividendRecord] = []
    for _, row in df.iterrows():
        fiscal_year = str(row.get("财政年度", "")).strip()
        if not fiscal_year:
            continue
        plan = str(row.get("分红方案", ""))
        dps_value = parse_hk_dividend_per_share(plan)
        if dps_value is None or dps_value <= 0:
            continue
        records.append(
            DividendRecord(
                fiscal_year=fiscal_year,
                dividend_per_share=DividendPerShare(amount=dps_value, currency=currency),
                dividend_type=DividendType.CASH,
                announcement_date=_parse_date(row.get("公告日期")),
                ex_dividend_date=_parse_date(row.get("除净日")),
                payment_date=_parse_date(row.get("派息日")),
            )
        )
    return records


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    try:
        ts = pd.to_datetime(val, errors="coerce")
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if pd.isna(f):
        return None
    return f
