"""Security aggregate assembly: composes Symbol/Exchange/Profile/Company/Snapshot.

Loaders are split by cost: ``get_security`` fires one lightweight static-info
call; ``get_market_cap_history`` pulls daily K-line + share history and is
materially heavier. ``load_security_with_history`` is a composite helper for
callers that genuinely need both; everything else should pick the leaner
loader to avoid paying the historical-series cost unnecessarily.
"""

from __future__ import annotations

import logging
from datetime import datetime

from backend.domain.stocks.company import Company
from backend.domain.stocks.exchange import exchange_for_symbol
from backend.domain.stocks.market import Market
from backend.domain.stocks.market_cap_history import MarketCapHistory
from backend.domain.stocks.profile import Profile
from backend.domain.stocks.security import Security
from backend.domain.stocks.snapshot import StockSnapshot
from backend.domain.stocks.symbol import Symbol
from backend.infrastructure.parsers import DEFAULT_WINDOW_YEARS
from backend.infrastructure.sources import (
    eastmoney_hk,
    load_market_cap_frame,
    monthly_mcap_rows,
    xueqiu,
)
from backend.infrastructure.symbol_resolver import parse_symbol

logger = logging.getLogger(__name__)


_YI = 1e8


def _fetch_stock_info(symbol: str) -> tuple[Symbol, dict]:
    sym = parse_symbol(symbol)
    if sym.market is Market.HK:
        return sym, eastmoney_hk.fetch_stock_info_hk(sym.code)
    return sym, xueqiu.fetch_stock_info_a(sym.code)


def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        result = float(val)
    except (TypeError, ValueError):
        return None
    return result if result else None


def _build_profile(info: dict, sym: Symbol) -> Profile:
    name = str(info.get("股票简称") or sym.code).strip()
    list_date = info.get("上市日期") or info.get("成立日期")
    return Profile(
        name=name,
        list_date=str(list_date).strip() if list_date else None,
    )


def _build_company(info: dict, mkt: Market) -> Company:
    legal_name = str(info.get("股票简称") or "").strip()
    industry = info.get("行业")
    return Company(
        legal_name=legal_name,
        industry=str(industry).strip() if industry else None,
        region=mkt.default_region,
    )


def _build_latest_snapshot(info: dict, sym: Symbol) -> StockSnapshot:
    current_price = _to_float(info.get("最新"))
    market_cap = _to_float(info.get("总市值"))
    total_shares = _to_float(info.get("总股本"))
    if not current_price and market_cap and total_shares:
        current_price = market_cap / total_shares
    return StockSnapshot(
        symbol=sym,
        current_price=current_price,
        market_cap=market_cap,
        total_shares=total_shares,
        as_of=datetime.utcnow(),
    )


def get_security(symbol: str) -> Security:
    """Assemble the ``Security`` aggregate from upstream snapshot data.

    A single upstream call yields the static security/company attributes
    *and* the latest market quote, so they are composed together here.
    Historical market-cap is loaded separately via ``get_market_cap_history``
    to avoid paying its cost when not needed.
    """
    sym, info = _fetch_stock_info(symbol)
    profile = _build_profile(info, sym)
    company = _build_company(info, sym.market)
    latest_snapshot = _build_latest_snapshot(info, sym)
    exchange = exchange_for_symbol(sym)
    return Security(
        symbol=sym,
        exchange=exchange,
        profile=profile,
        company=company,
        latest_snapshot=latest_snapshot,
    )


def get_market_cap_history(
    symbol: str, window_years: int = DEFAULT_WINDOW_YEARS
) -> MarketCapHistory:
    """Calendar-month market cap (yuan) over the rolling window.

    The infrastructure layer hands us values in 亿; we convert to raw yuan
    here so the value object exposed to the domain stays unit-consistent
    with ``StockSnapshot.market_cap``. Caching is delegated to the
    underlying source-layer calls (daily prices + share history).
    """
    sym = parse_symbol(symbol)
    df = load_market_cap_frame(sym.market, sym.code, window_years, period="monthly")
    if df.empty:
        return MarketCapHistory()
    rows_yi = monthly_mcap_rows(df)
    return MarketCapHistory.from_pairs(
        (period, value_yi * _YI) for period, value_yi in rows_yi
    )


def load_security_with_history(
    symbol: str, window_years: int = DEFAULT_WINDOW_YEARS
) -> Security:
    """Composite loader: ``Security`` with its monthly market-cap history attached.

    Convenience for callers (e.g. analysis context assembly) that need both
    the static aggregate and the historical valuation series. Pays the cost
    of both upstream calls; prefer the individual loaders when only one
    side is required.
    """
    security = get_security(symbol)
    history = get_market_cap_history(symbol, window_years=window_years)
    return security.with_market_cap_history(history)
