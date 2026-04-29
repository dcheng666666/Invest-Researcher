"""Pure value/text parsers for raw data from upstream APIs.

These helpers normalize Chinese number formats, percentage strings, and
report-period labels into clean Python values. They have **no IO and no
state** — only string/number transformations.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

import pandas as pd

from backend.domain.financials.period import ReportPeriod


DEFAULT_WINDOW_YEARS = 10

QUARTER_MAP: dict[int, str] = {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}


def rolling_window_cutoff(years: int = DEFAULT_WINDOW_YEARS) -> pd.Timestamp:
    """Lower bound date: include report periods on or after (today - years)."""
    return pd.Timestamp.now().normalize() - pd.DateOffset(years=years)


def parse_report_period(val) -> pd.Timestamp:
    """Parse a 报告期 cell (e.g. 20241231, '2024-12-31') to a normalized timestamp."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return pd.NaT
    raw = str(val).strip()
    compact = raw.replace("-", "").replace("/", "")[:8]
    if len(compact) >= 8 and compact.isdigit():
        return pd.to_datetime(compact, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(raw, errors="coerce")


def to_quarter_label(val) -> str:
    """Convert a report-period value to a quarter label like '2024Q1'."""
    ts = parse_report_period(val)
    if pd.isna(ts):
        raw = str(val).strip().replace("-", "").replace("/", "")[:8]
        if len(raw) >= 8 and raw.isdigit():
            month = int(raw[4:6])
            return f"{raw[:4]}{QUARTER_MAP.get(month, 'Q?')}"
        return str(val)[:4]
    return f"{ts.year}{QUARTER_MAP.get(ts.month, 'Q?')}"


def report_period_from_value(val) -> ReportPeriod | None:
    """Construct a ``ReportPeriod`` from a raw report-period cell.

    Returns ``None`` when the input cannot be parsed as a quarter-end date.
    """
    ts = parse_report_period(val)
    if pd.isna(ts):
        return None
    month = int(ts.month)
    quarter = QUARTER_MAP.get(month)
    if quarter is None:
        return None
    period_end = date(int(ts.year), month, int(ts.day))
    return ReportPeriod.quarterly(int(ts.year), int(quarter[1]), period_end)


def report_on_or_after_cutoff(val, cutoff: pd.Timestamp) -> bool:
    ts = parse_report_period(val)
    if pd.isna(ts):
        try:
            return int(str(val)[:4]) >= cutoff.year
        except (ValueError, TypeError):
            return False
    return ts.normalize() >= cutoff.normalize()


def parse_cn_number(val) -> float | None:
    """Parse Chinese formatted numbers like '196.10亿', '9238.22万', '1.01万亿' to float (yuan).

    ``万亿`` must be handled before a bare ``(亿|万)`` match; otherwise ``1.01万亿``
    incorrectly becomes 1.01 * 1e4 (the ``万`` in ``万亿`` wins), which breaks
    cumulative revenue de-accumulation and TTM charts for mega-caps like 600941.
    """
    if val is None or val is False:
        return None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if isinstance(val, float) and pd.isna(val):
            return None
        return float(val)

    s = str(val).strip()
    if s in ("", "False", "--", "nan", "NaN"):
        return None
    s = s.replace(",", "")

    m_trillion = re.match(r"^(-?[\d.]+)\s*万亿", s)
    if m_trillion:
        return float(m_trillion.group(1)) * 1e12

    m = re.match(r"^(-?[\d.]+)(亿|万)", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "亿":
            return num * 1e8
        return num * 1e4

    try:
        return float(s)
    except ValueError:
        return None


def parse_pct(val) -> float | None:
    """Parse percentage string like '23.38%' to float 0.2338."""
    if val is None or val is False or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace("%", "")
    if s in ("", "False", "--", "nan", "NaN"):
        return None
    try:
        return float(s) / 100.0
    except ValueError:
        return None


def hk_float(val) -> float | None:
    if val is None or val is False or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def hk_ratio_from_pct_field(val) -> float | None:
    """Eastmoney HK fields are plain numbers meaning percent (e.g. 12.3 -> 12.3%)."""
    x = hk_float(val)
    if x is None:
        return None
    return x / 100.0


def hk_yoy_ratio(val) -> float | None:
    x = hk_float(val)
    if x is None:
        return None
    return x / 100.0


def hk_report_ts(val) -> pd.Timestamp:
    ts = pd.to_datetime(val, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    return ts.normalize()


def hk_period_label_from_report_date(val) -> str:
    ts = hk_report_ts(val)
    if pd.isna(ts):
        return str(val)[:8]
    q = (int(ts.month) - 1) // 3 + 1
    return f"{ts.year}Q{q}"


def normalize_hk_indicator_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if len(df.columns) == 1:
        col = df.columns[0]
        nested = df[col].dropna()
        if nested.empty:
            return pd.DataFrame()
        if isinstance(nested.iloc[0], dict):
            return pd.json_normalize(nested)
    return df


HKIndicatorMode = Literal["报告期", "年度"]


_HK_DPS_PATTERNS = [
    re.compile(r"每股派港币([\d.]+)元"),
    re.compile(r"相当于每股派([\d.]+)港元"),
]


def parse_hk_dividend_per_share(plan_text: str) -> float | None:
    """Extract per-share cash dividend (HKD) from an HK 分红方案 free-text field."""
    if not plan_text:
        return None
    for pat in _HK_DPS_PATTERNS:
        m = pat.search(plan_text)
        if m:
            return float(m.group(1))
    return None


# Boundary month between "previous-FY final dividend" and "current-FY interim
# dividend" implementations on THS A-share data. THS exposes 公告日期 (the
# implementation announcement date) but no fiscal-year column, so the
# repository has to infer the fiscal year from the calendar timing of the
# implementation. Empirically (招行/工行/中国平安/茅台/平安银行 2010-2025):
#   * Previous-FY final dividends implement Apr-Jul (latest typically Jul 9).
#   * Current-FY interim / Q3 / year-end specials implement Aug-Dec (or Jan
#     of the following year, when very late).
# A boundary at month 7 catches the platinum case 中国平安 2016-2019 中期分红
# (implemented Aug 26-30) which a month-8 boundary would mis-bucket.
_THS_FY_BOUNDARY_MONTH = 7


def ths_fiscal_year_from_announcement(announce: date) -> str:
    """Infer the fiscal year a THS A-share dividend implementation belongs to.

    A-share annual reports (and their final dividend proposals) are filed
    by April 30 of year ``Y``; interim reports are filed by August 30. So
    an implementation announced on or before July of year ``Y`` is the final
    dividend of FY(Y-1); after July it belongs to the current FY(Y).
    """
    return str(announce.year - 1) if announce.month <= _THS_FY_BOUNDARY_MONTH else str(announce.year)
