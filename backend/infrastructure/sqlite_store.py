"""Local SQLite store for stock symbol metadata."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "stock_symbols.db"

_empty_db_warned = False

DDL = """
CREATE TABLE IF NOT EXISTS stock_symbols (
    market TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (market, code)
);
CREATE INDEX IF NOT EXISTS idx_stock_symbols_name ON stock_symbols(name);
CREATE INDEX IF NOT EXISTS idx_stock_symbols_code ON stock_symbols(code);

CREATE TABLE IF NOT EXISTS industry_benchmarks (
    industry_key TEXT NOT NULL PRIMARY KEY,
    as_of TEXT NOT NULL,
    roe_median REAL,
    roa_median REAL,
    gross_margin_median REAL,
    debt_ratio_median REAL,
    source_note TEXT
);
"""


def default_db_path() -> Path:
    return DEFAULT_DB_PATH


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)


def initialize_store(db_path: Path | None = None) -> None:
    """Ensure local symbol DB file and schema exist."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        conn.commit()
    finally:
        conn.close()


def replace_all_symbols(
    rows: list[tuple[str, str, str]], db_path: Path | None = None
) -> None:
    """Replace entire table with (market, code, name) rows in one transaction."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    unique: dict[tuple[str, str], tuple[str, str, str]] = {}
    for m, c, n in rows:
        unique[(m, str(c).strip())] = (m, str(c).strip(), str(n).strip())
    deduped = list(unique.values())
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        conn.execute("DELETE FROM stock_symbols")
        conn.executemany(
            "INSERT INTO stock_symbols (market, code, name) VALUES (?, ?, ?)",
            deduped,
        )
        conn.commit()
        logger.info("Stock symbols DB replaced: %d rows at %s", len(deduped), path)
    finally:
        conn.close()


def search_symbols(
    query: str, limit: int = 10, db_path: Path | None = None
) -> list[dict]:
    global _empty_db_warned
    q = query.strip()
    if not q:
        return []

    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        if not _empty_db_warned:
            logger.warning(
                "Stock symbol DB missing at %s; run scripts/sync_stock_symbols.py",
                path,
            )
            _empty_db_warned = True
        return []

    like = f"%{q}%"

    conn = sqlite3.connect(str(path))
    try:
        cur = conn.execute(
            "SELECT code, name, market FROM stock_symbols "
            "WHERE (name LIKE ? OR code LIKE ?) LIMIT ?",
            (like, like, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    logger.debug("Symbol search q=%r limit=%d -> %d rows", q, limit, len(rows))
    return [
        {"code": str(r[0]), "name": str(r[1]).strip(), "market": str(r[2])}
        for r in rows
    ]


def lookup_by_market_code(
    market: str, code: str, db_path: Path | None = None
) -> dict | None:
    """Fetch a single row from local SQLite by exact (market, code); None if absent."""
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return None

    conn = sqlite3.connect(str(path))
    try:
        cur = conn.execute(
            "SELECT code, name, market FROM stock_symbols WHERE market = ? AND code = ?",
            (market, code),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return {"code": str(row[0]), "name": str(row[1]).strip(), "market": str(row[2])}


# --------------------------------------------------------------------------- #
# Industry benchmarks (same SQLite file as stock_symbols)
# --------------------------------------------------------------------------- #


def get_industry_benchmark_row(
    industry_key: str, db_path: Path | None = None
) -> dict | None:
    """Return one benchmark row by exact ``industry_key``; None if missing."""
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return None
    key = str(industry_key).strip()
    if not key:
        return None

    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT industry_key, as_of, roe_median, roa_median, "
            "gross_margin_median, debt_ratio_median, source_note "
            "FROM industry_benchmarks WHERE industry_key = ?",
            (key,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return {
        "industry_key": str(row[0]),
        "as_of": str(row[1]),
        "roe_median": row[2],
        "roa_median": row[3],
        "gross_margin_median": row[4],
        "debt_ratio_median": row[5],
        "source_note": None if row[6] is None else str(row[6]),
    }


def replace_all_industry_benchmarks(
    rows: list[tuple[str, str, float | None, float | None, float | None, float | None, str | None]],
    db_path: Path | None = None,
) -> None:
    """Replace entire ``industry_benchmarks`` table.

    Each row is
    ``(industry_key, as_of, roe_median, roa_median, gross_margin_median, debt_ratio_median, source_note)``.
    """
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        conn.execute("DELETE FROM industry_benchmarks")
        conn.executemany(
            "INSERT INTO industry_benchmarks ("
            "industry_key, as_of, roe_median, roa_median, "
            "gross_margin_median, debt_ratio_median, source_note"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        logger.info(
            "Industry benchmarks DB replaced: %d rows at %s", len(rows), path
        )
    finally:
        conn.close()
