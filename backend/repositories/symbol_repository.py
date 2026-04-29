"""Symbol lookup / search / sync, backed by local SQLite."""

from __future__ import annotations

from pathlib import Path

from backend.domain.stocks.market import Market
from backend.infrastructure import sqlite_store
from backend.infrastructure.symbol_resolver import parse_symbol


def _db_market_for_a_share(code: str) -> str:
    """Align with stock_lists.a_share_market_for_code (DB primary key partition)."""
    c = str(code).strip()
    if c.startswith("6"):
        return "SH"
    if c.startswith(("0", "3")):
        return "SZ"
    return "OTHER"


def initialize(db_path: Path | None = None) -> None:
    sqlite_store.initialize_store(db_path)


def replace_all(
    rows: list[tuple[str, str, str]], db_path: Path | None = None
) -> None:
    sqlite_store.replace_all_symbols(rows, db_path)


def search(query: str, limit: int = 10, db_path: Path | None = None) -> list[dict]:
    return sqlite_store.search_symbols(query, limit=limit, db_path=db_path)


def lookup(symbol: str, db_path: Path | None = None) -> dict | None:
    """Resolve user input to one row from local SQLite; ``None`` when missing."""
    canonical = parse_symbol(symbol)
    if canonical.market is Market.HK:
        market, code = "HK", canonical.code
    else:
        market, code = _db_market_for_a_share(canonical.code), canonical.code
    return sqlite_store.lookup_by_market_code(market, code, db_path=db_path)


def display_name(symbol: str) -> str:
    row = lookup(symbol)
    return row["name"] if row else symbol


def default_db_path() -> Path:
    return sqlite_store.default_db_path()
