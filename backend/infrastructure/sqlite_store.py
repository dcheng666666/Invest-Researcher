"""Local SQLite store for stock symbol metadata."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

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

CREATE TABLE IF NOT EXISTS valuation_screen_runs (
    refresh_date TEXT NOT NULL PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS valuation_screen_rows (
    refresh_date TEXT NOT NULL,
    market TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    board TEXT NOT NULL,
    overall_score REAL,
    valuation_score INTEGER,
    valuation_verdict TEXT,
    pe_percentile REAL,
    peg REAL,
    current_pe REAL,
    results_json TEXT NOT NULL,
    errors_json TEXT NOT NULL,
    scores_json TEXT NOT NULL,
    error TEXT,
    PRIMARY KEY (refresh_date, market, code)
);
CREATE INDEX IF NOT EXISTS idx_val_screen_rows_date_board
    ON valuation_screen_rows(refresh_date, board);
CREATE INDEX IF NOT EXISTS idx_val_screen_rows_overall
    ON valuation_screen_rows(refresh_date, overall_score);
CREATE INDEX IF NOT EXISTS idx_val_screen_rows_val_score
    ON valuation_screen_rows(refresh_date, valuation_score);
CREATE INDEX IF NOT EXISTS idx_val_screen_rows_name
    ON valuation_screen_rows(name);
CREATE INDEX IF NOT EXISTS idx_val_screen_rows_code
    ON valuation_screen_rows(code);
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


# --------------------------------------------------------------------------- #
# STAR / ChiNext universe + valuation screening (same SQLite file)
# --------------------------------------------------------------------------- #


def classify_star_chinext_board(market: str, code: str) -> str | None:
    """Return ``STAR``, ``CHINEXT``, or ``None`` if not in screened boards."""
    m = str(market).strip().upper()
    c = str(code).strip()
    if m == "SH" and c.startswith("688"):
        return "STAR"
    if m == "SZ" and (c.startswith("300") or c.startswith("301")):
        return "CHINEXT"
    return None


def list_star_chinext_symbols(db_path: Path | None = None) -> list[dict[str, str]]:
    """Listed STAR + ChiNext rows from ``stock_symbols`` (market, code, name)."""
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return []

    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT market, code, name FROM stock_symbols WHERE "
            "(market = 'SH' AND code GLOB '688*') OR "
            "(market = 'SZ' AND (code GLOB '300*' OR code GLOB '301*')) "
            "ORDER BY market, code"
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    out: list[dict[str, str]] = []
    for r in rows:
        m, c, n = str(r[0]), str(r[1]).strip(), str(r[2]).strip()
        if classify_star_chinext_board(m, c):
            out.append({"market": m, "code": c, "name": n})
    return out


def get_valuation_run(
    refresh_date: str, db_path: Path | None = None
) -> dict[str, Any] | None:
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return None
    d = str(refresh_date).strip()
    if not d:
        return None

    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT refresh_date, started_at, finished_at, notes "
            "FROM valuation_screen_runs WHERE refresh_date = ?",
            (d,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return {
        "refresh_date": str(row[0]),
        "started_at": str(row[1]),
        "finished_at": None if row[2] is None else str(row[2]),
        "notes": None if row[3] is None else str(row[3]),
    }


def ensure_valuation_run_started(
    refresh_date: str,
    started_at: str,
    *,
    notes: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Insert run row if missing (``INSERT OR IGNORE``)."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        conn.execute(
            "INSERT OR IGNORE INTO valuation_screen_runs "
            "(refresh_date, started_at, finished_at, notes) VALUES (?, ?, NULL, ?)",
            (str(refresh_date).strip(), started_at, notes),
        )
        conn.commit()
    finally:
        conn.close()


def mark_valuation_run_finished(refresh_date: str, db_path: Path | None = None) -> None:
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return
    finished = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        conn.execute(
            "UPDATE valuation_screen_runs SET finished_at = ? WHERE refresh_date = ?",
            (finished, str(refresh_date).strip()),
        )
        conn.commit()
    finally:
        conn.close()


def valuation_codes_done_for_date(
    refresh_date: str, db_path: Path | None = None
) -> set[tuple[str, str]]:
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return set()
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT market, code FROM valuation_screen_rows WHERE refresh_date = ?",
            (str(refresh_date).strip(),),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return {(str(r[0]), str(r[1])) for r in rows}


def _json_normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_normalize(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    return obj


def dumps_analysis_payload(
    results: dict[int, Any], errors: dict[int, str], scores: list[int]
) -> tuple[str, str, str]:
    """Serialize ``run_steps`` outputs to JSON strings for SQLite."""
    results_ser = _json_normalize(results)
    errors_ser = {str(k): v for k, v in errors.items()}
    payload_results = json.dumps(results_ser, ensure_ascii=False)
    payload_errors = json.dumps(errors_ser, ensure_ascii=False)
    payload_scores = json.dumps(scores, ensure_ascii=False)
    return payload_results, payload_errors, payload_scores


def insert_valuation_screen_row(
    *,
    refresh_date: str,
    market: str,
    code: str,
    name: str,
    board: str,
    overall_score: float | None,
    valuation_score: int | None,
    valuation_verdict: str | None,
    pe_percentile: float | None,
    peg: float | None,
    current_pe: float | None,
    results_json: str,
    errors_json: str,
    scores_json: str,
    error: str | None,
    conn: sqlite3.Connection,
) -> None:
    conn.execute(
        "INSERT INTO valuation_screen_rows ("
        "refresh_date, market, code, name, board, "
        "overall_score, valuation_score, valuation_verdict, "
        "pe_percentile, peg, current_pe, "
        "results_json, errors_json, scores_json, error"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            str(refresh_date).strip(),
            str(market).strip(),
            str(code).strip(),
            str(name).strip(),
            str(board).strip(),
            overall_score,
            valuation_score,
            valuation_verdict,
            pe_percentile,
            peg,
            current_pe,
            results_json,
            errors_json,
            scores_json,
            error,
        ),
    )


def get_latest_completed_refresh_date(db_path: Path | None = None) -> str | None:
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return None
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT refresh_date FROM valuation_screen_runs "
            "WHERE finished_at IS NOT NULL "
            "ORDER BY refresh_date DESC LIMIT 1"
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return None if not row else str(row[0])


def get_latest_refresh_date_with_any_rows(db_path: Path | None = None) -> str | None:
    """Latest ``refresh_date`` that has at least one screening row (includes partial runs)."""
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return None
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute("SELECT MAX(refresh_date) FROM valuation_screen_rows")
        row = cur.fetchone()
    finally:
        conn.close()
    if not row or row[0] is None:
        return None
    return str(row[0])


def get_default_valuation_screen_refresh_date(db_path: Path | None = None) -> str | None:
    """Default list date: last closed run, else any date that already has stored rows."""
    closed = get_latest_completed_refresh_date(db_path)
    if closed:
        return closed
    return get_latest_refresh_date_with_any_rows(db_path)


def list_refresh_dates_with_completed_runs(
    limit: int = 30, db_path: Path | None = None
) -> list[str]:
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return []
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT refresh_date FROM valuation_screen_runs "
            "WHERE finished_at IS NOT NULL "
            "ORDER BY refresh_date DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [str(r[0]) for r in rows]


def list_refresh_dates_having_rows(
    limit: int = 30, db_path: Path | None = None
) -> list[str]:
    """Distinct ``refresh_date`` values that have screening rows (partial or complete)."""
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return []
    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT DISTINCT refresh_date FROM valuation_screen_rows "
            "ORDER BY refresh_date DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [str(r[0]) for r in rows]


def query_valuation_screen_rows(
    *,
    refresh_date: str,
    board: str | None = None,
    overall_verdict_sql: str | None = None,
    step_score_bounds: list[tuple[int | None, int | None]] | None = None,
    sort_clauses: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
    db_path: Path | None = None,
) -> tuple[list[dict[str, Any]], int]:
    path = db_path or DEFAULT_DB_PATH
    if not path.is_file():
        return [], 0

    rd = str(refresh_date).strip()
    where: list[str] = ["refresh_date = ?"]
    params: list[Any] = [rd]

    if board and board.upper() not in ("ALL", ""):
        where.append("board = ?")
        params.append(str(board).strip().upper())

    if overall_verdict_sql:
        where.append(overall_verdict_sql)

    if step_score_bounds:
        for idx, (lo, hi) in enumerate(step_score_bounds):
            if lo is not None:
                where.append(
                    "CAST(json_extract(scores_json, ?) AS INTEGER) >= ?"
                )
                params.extend((f"$[{idx}]", lo))
            if hi is not None:
                where.append(
                    "CAST(json_extract(scores_json, ?) AS INTEGER) <= ?"
                )
                params.extend((f"$[{idx}]", hi))

    wh = " AND ".join(where)
    _orders: dict[str, str] = {
        "overall_desc": "overall_score DESC NULLS LAST",
        "overall_asc": "overall_score ASC NULLS LAST",
    }
    for si in range(5):
        _orders[f"step{si + 1}_desc"] = (
            f"CAST(json_extract(scores_json, '$[{si}]') AS INTEGER) "
            "DESC NULLS LAST"
        )
        _orders[f"step{si + 1}_asc"] = (
            f"CAST(json_extract(scores_json, '$[{si}]') AS INTEGER) "
            "ASC NULLS LAST"
        )
    clauses = sort_clauses if sort_clauses else ["overall_desc"]
    order_sql = ", ".join(_orders[t] for t in clauses)

    conn = sqlite3.connect(str(path))
    try:
        init_db(conn)
        cur = conn.execute(
            f"SELECT COUNT(*) FROM valuation_screen_rows WHERE {wh}", params
        )
        total = int(cur.fetchone()[0])

        cur2 = conn.execute(
            f"SELECT refresh_date, market, code, name, board, overall_score, "
            f"valuation_score, valuation_verdict, pe_percentile, peg, current_pe, "
            f"errors_json, error, scores_json "
            f"FROM valuation_screen_rows WHERE {wh} "
            f"ORDER BY {order_sql} "
            f"LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        raw = cur2.fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for r in raw:
        err_json = str(r[11])
        step_errors: dict[str, str] = {}
        try:
            parsed = json.loads(err_json)
            if isinstance(parsed, dict):
                step_errors = {str(k): str(v) for k, v in parsed.items() if v}
        except json.JSONDecodeError:
            pass
        scores_raw = str(r[13])
        step_scores: list[int] | None = None
        try:
            sp = json.loads(scores_raw)
            if isinstance(sp, list):
                step_scores = [int(x) for x in sp]
        except (json.JSONDecodeError, TypeError, ValueError):
            step_scores = None
        out.append(
            {
                "refresh_date": str(r[0]),
                "market": str(r[1]),
                "code": str(r[2]),
                "name": str(r[3]),
                "board": str(r[4]),
                "overall_score": r[5],
                "valuation_score": r[6],
                "valuation_verdict": r[7],
                "pe_percentile": r[8],
                "peg": r[9],
                "current_pe": r[10],
                "step_errors": step_errors,
                "error": r[12],
                "step_scores": step_scores,
            }
        )
    return out, total
