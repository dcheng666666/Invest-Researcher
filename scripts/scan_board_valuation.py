#!/usr/bin/env python3
"""Batch-run five-step analysis for a chosen universe and persist results to SQLite.

Universes:
  - ``star``: Shanghai STAR (688*).
  - ``chinext``: Shenzhen ChiNext (300*/301*).
  - ``sh_main``: Shanghai main board (600/601/603/605*).
  - ``sz_main``: Shenzhen main board (000/001/002*, ex ChiNext).
  - ``hk``: Hong Kong main board (HK market symbols).

One refresh per calendar ``refresh_date`` and ``scan_scope``. Resume skips codes
already stored for that pair. Uses ``build_context`` + ``run_steps`` (same as
single-stock / Excel export).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scan_board_valuation")

from backend.application.analysis import service as analysis_service
from backend.application.analysis.score_aggregator import overall_score as compute_overall_score
from backend.domain.verdict import Verdict
from backend.infrastructure.sqlite_store import (
    SCAN_SCOPE_SZ_MAIN,
    classify_star_chinext_board,
    classify_sz_main_board,
    default_db_path,
    dumps_analysis_payload,
    ensure_valuation_run_started,
    get_valuation_run,
    init_db,
    insert_valuation_screen_row,
    list_star_chinext_symbols,
    list_sz_main_board_symbols,
    mark_valuation_run_finished,
    valuation_codes_done_for_date,
)


def _classify_sh_main_board(market: str, code: str) -> str | None:
    m = str(market).strip().upper()
    c = str(code).strip()
    if m != "SH":
        return None
    if c.startswith(("600", "601", "603", "605")):
        return "SH_MAIN"
    return None


def _classify_hk_board(market: str, code: str) -> str | None:
    m = str(market).strip().upper()
    c = str(code).strip()
    if m != "HK":
        return None
    if c:
        return "HK_MAIN"
    return None


def _list_sh_main_board_symbols(db_path: Path) -> list[dict[str, str]]:
    if not db_path.is_file():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT market, code, name FROM stock_symbols WHERE "
            "market = 'SH' AND ("
            "code GLOB '600*' OR code GLOB '601*' OR "
            "code GLOB '603*' OR code GLOB '605*'"
            ") ORDER BY code"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    out: list[dict[str, str]] = []
    for r in rows:
        m, c, n = str(r[0]), str(r[1]).strip(), str(r[2]).strip()
        if _classify_sh_main_board(m, c):
            out.append({"market": m, "code": c, "name": n})
    return out


def _list_hk_symbols(db_path: Path) -> list[dict[str, str]]:
    if not db_path.is_file():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        init_db(conn)
        cur = conn.execute(
            "SELECT market, code, name FROM stock_symbols "
            "WHERE market = 'HK' ORDER BY code"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    out: list[dict[str, str]] = []
    for r in rows:
        m, c, n = str(r[0]), str(r[1]).strip(), str(r[2]).strip()
        if _classify_hk_board(m, c):
            out.append({"market": m, "code": c, "name": n})
    return out


def _verdict_to_str(v: object | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, Verdict):
        return v.value
    s = str(v).strip().lower()
    return s if s else None


def _extract_valuation_fields(
    results: dict[int, dict],
) -> tuple[int | None, str | None, float | None, float | None, float | None]:
    r5 = results.get(5)
    if not isinstance(r5, dict):
        return None, None, None, None, None
    score = r5.get("score")
    vscore = int(score) if score is not None else None
    vver = _verdict_to_str(r5.get("verdict"))
    pe_pct = r5.get("pe_percentile")
    pe_pct_f = float(pe_pct) if pe_pct is not None else None
    peg = r5.get("peg")
    peg_f = float(peg) if peg is not None else None
    cpe = r5.get("current_pe")
    cpe_f = float(cpe) if cpe is not None else None
    return vscore, vver, pe_pct_f, peg_f, cpe_f


def _dedupe_symbols(symbols: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for item in symbols:
        key = (item["market"], item["code"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run 5-step analysis for STAR, ChiNext, SH main, SZ main, or HK board, store in SQLite."
    )
    parser.add_argument(
        "--universe",
        choices=("star", "chinext", "sh_main", "sz_main", "hk"),
        default="star",
        help=(
            "star: SH 688*; chinext: SZ 300/301*; "
            "sh_main: SH 600/601/603/605*; sz_main: SZ 000/001/002*; "
            "hk: HK market symbols"
        ),
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Refresh calendar date YYYY-MM-DD (default: local today)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to stock_symbols.db (default: data/stock_symbols.db under project)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        help="Seconds to sleep after each stock (default: 5; set 0 to disable)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of stocks to analyze this invocation (excluding skips)",
    )
    args = parser.parse_args()

    db_path = Path(args.db).resolve() if args.db else default_db_path()

    if args.universe == "star":
        scan_scope = "star"
        notes = "STAR"
        empty_msg = (
            "No STAR symbols in local DB; run scripts/sync_stock_symbols.py first."
        )

        def list_symbols(*, db_path: Path | None = None) -> list[dict[str, str]]:
            rows = list_star_chinext_symbols(db_path=db_path)
            return [
                s
                for s in rows
                if classify_star_chinext_board(s["market"], s["code"]) == "STAR"
            ]

        def classify_board(market: str, code: str) -> str | None:
            board = classify_star_chinext_board(market, code)
            return board if board == "STAR" else None

    elif args.universe == "chinext":
        scan_scope = "chinext"
        notes = "CHINEXT"
        empty_msg = (
            "No ChiNext symbols in local DB; run scripts/sync_stock_symbols.py first."
        )

        def list_symbols(*, db_path: Path | None = None) -> list[dict[str, str]]:
            rows = list_star_chinext_symbols(db_path=db_path)
            return [
                s
                for s in rows
                if classify_star_chinext_board(s["market"], s["code"]) == "CHINEXT"
            ]

        def classify_board(market: str, code: str) -> str | None:
            board = classify_star_chinext_board(market, code)
            return board if board == "CHINEXT" else None
    elif args.universe == "sh_main":
        scan_scope = "sh_main"

        def list_symbols(*, db_path: Path | None = None) -> list[dict[str, str]]:
            if db_path is None:
                raise ValueError("db_path is required for sh_main listing")
            return _list_sh_main_board_symbols(db_path)

        classify_board = _classify_sh_main_board
        notes = "SH_MAIN_BOARD"
        empty_msg = (
            "No Shanghai main-board symbols in local DB; "
            "run scripts/sync_stock_symbols.py first."
        )
    elif args.universe == "hk":
        scan_scope = "hk"

        def list_symbols(*, db_path: Path | None = None) -> list[dict[str, str]]:
            if db_path is None:
                raise ValueError("db_path is required for hk listing")
            return _list_hk_symbols(db_path)

        classify_board = _classify_hk_board
        notes = "HK_MAIN_BOARD"
        empty_msg = (
            "No Hong Kong symbols in local DB; "
            "run scripts/sync_stock_symbols.py first."
        )
    else:
        scan_scope = SCAN_SCOPE_SZ_MAIN
        list_symbols = list_sz_main_board_symbols
        classify_board = classify_sz_main_board
        notes = "SZ_MAIN_BOARD"
        empty_msg = (
            "No Shenzhen main-board symbols in local DB; "
            "run scripts/sync_stock_symbols.py first."
        )

    if args.date:
        refresh_date = str(args.date).strip()
    else:
        refresh_date = date.today().isoformat()

    run = get_valuation_run(refresh_date, scan_scope=scan_scope, db_path=db_path)
    if run and run.get("finished_at"):
        print(
            f"Refresh {refresh_date} scope={scan_scope} already completed "
            f"(finished_at={run['finished_at']}). Exiting.",
            file=sys.stderr,
        )
        sys.exit(0)

    raw_universe = list_symbols(db_path=db_path)
    universe = _dedupe_symbols(raw_universe)
    duplicate_count = len(raw_universe) - len(universe)
    if duplicate_count:
        logger.warning(
            "Filtered %d duplicated symbols in universe=%s",
            duplicate_count,
            scan_scope,
        )
    if not universe:
        print(empty_msg, file=sys.stderr)
        sys.exit(1)

    done = valuation_codes_done_for_date(
        refresh_date, scan_scope=scan_scope, db_path=db_path
    )
    remaining = [s for s in universe if (s["market"], s["code"]) not in done]
    if args.limit is not None:
        pending = remaining[: max(0, args.limit)]
    else:
        pending = remaining

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ensure_valuation_run_started(
        refresh_date,
        started_at,
        scan_scope=scan_scope,
        notes=notes,
        db_path=db_path,
    )

    if not remaining:
        mark_valuation_run_finished(
            refresh_date, scan_scope=scan_scope, db_path=db_path
        )
        print(
            f"refresh_date={refresh_date} scan_scope={scan_scope}: "
            f"all {len(universe)} symbols already stored; marked run finished."
        )
        sys.exit(0)

    print(
        f"refresh_date={refresh_date} scan_scope={scan_scope} universe={len(universe)} "
        f"already_done={len(done)} to_process_this_run={len(pending)} db={db_path}"
    )

    conn = sqlite3.connect(str(db_path))
    try:
        init_db(conn)

        ok = 0
        fail = 0
        for i, sym in enumerate(pending, start=1):
            market, code, name = sym["market"], sym["code"], sym["name"]
            board = classify_board(market, code)
            if not board:
                continue

            logger.info("[%d/%d] %s %s %s", i, len(pending), market, code, name)

            try:
                ctx = analysis_service.build_context(code)
            except Exception as e:
                logger.exception("build_context raised for %s", code)
                rj, ej, sj = dumps_analysis_payload({}, {}, [])
                insert_valuation_screen_row(
                    refresh_date=refresh_date,
                    scan_scope=scan_scope,
                    market=market,
                    code=code,
                    name=name,
                    board=board,
                    overall_score=None,
                    valuation_score=None,
                    valuation_verdict=None,
                    pe_percentile=None,
                    peg=None,
                    current_pe=None,
                    results_json=rj,
                    errors_json=ej,
                    scores_json=sj,
                    error=f"build_context raised: {e}",
                    conn=conn,
                )
                conn.commit()
                fail += 1
                if args.sleep:
                    time.sleep(args.sleep)
                continue

            if ctx is None:
                rj, ej, sj = dumps_analysis_payload({}, {}, [])
                insert_valuation_screen_row(
                    refresh_date=refresh_date,
                    scan_scope=scan_scope,
                    market=market,
                    code=code,
                    name=name,
                    board=board,
                    overall_score=None,
                    valuation_score=None,
                    valuation_verdict=None,
                    pe_percentile=None,
                    peg=None,
                    current_pe=None,
                    results_json=rj,
                    errors_json=ej,
                    scores_json=sj,
                    error="No financial data (build_context returned None).",
                    conn=conn,
                )
                conn.commit()
                fail += 1
                if args.sleep:
                    time.sleep(args.sleep)
                continue

            try:
                results, errors, scores = analysis_service.run_steps(ctx)
            except Exception as e:
                logger.exception("run_steps raised for %s", code)
                rj, ej, sj = dumps_analysis_payload({}, {}, [])
                insert_valuation_screen_row(
                    refresh_date=refresh_date,
                    scan_scope=scan_scope,
                    market=market,
                    code=code,
                    name=name,
                    board=board,
                    overall_score=None,
                    valuation_score=None,
                    valuation_verdict=None,
                    pe_percentile=None,
                    peg=None,
                    current_pe=None,
                    results_json=rj,
                    errors_json=ej,
                    scores_json=sj,
                    error=f"run_steps raised: {e}",
                    conn=conn,
                )
                conn.commit()
                fail += 1
                if args.sleep:
                    time.sleep(args.sleep)
                continue

            overall = compute_overall_score(scores)
            vscore, vver, pe_pct_f, peg_f, cpe_f = _extract_valuation_fields(results)
            rj, ej, sj = dumps_analysis_payload(results, errors, scores)

            insert_valuation_screen_row(
                refresh_date=refresh_date,
                scan_scope=scan_scope,
                market=market,
                code=code,
                name=name,
                board=board,
                overall_score=overall,
                valuation_score=vscore,
                valuation_verdict=vver,
                pe_percentile=pe_pct_f,
                peg=peg_f,
                current_pe=cpe_f,
                results_json=rj,
                errors_json=ej,
                scores_json=sj,
                error=None,
                conn=conn,
            )
            conn.commit()
            ok += 1

            if args.sleep:
                time.sleep(args.sleep)

    finally:
        conn.close()

    done_after = valuation_codes_done_for_date(
        refresh_date, scan_scope=scan_scope, db_path=db_path
    )
    still = [s for s in universe if (s["market"], s["code"]) not in done_after]
    if not still:
        mark_valuation_run_finished(
            refresh_date, scan_scope=scan_scope, db_path=db_path
        )
        print(
            f"Finished refresh {refresh_date} scope={scan_scope}. "
            f"ok={ok} fail={fail} (run closed)."
        )
    else:
        print(
            f"Partial refresh {refresh_date} scope={scan_scope}. ok={ok} fail={fail} "
            f"remaining={len(still)} (run left open for resume)."
        )


if __name__ == "__main__":
    main()
