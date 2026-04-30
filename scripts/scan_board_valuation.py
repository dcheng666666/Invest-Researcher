#!/usr/bin/env python3
"""Scan STAR + ChiNext listings: run same analysis as single-stock API, persist to SQLite.

One refresh per calendar ``refresh_date`` (YYYY-MM-DD). Resume skips codes already
stored for that date. Uses ``build_context`` + ``run_steps`` (same as Excel export).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
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
    classify_star_chinext_board,
    default_db_path,
    dumps_analysis_payload,
    ensure_valuation_run_started,
    get_valuation_run,
    init_db,
    insert_valuation_screen_row,
    list_star_chinext_symbols,
    mark_valuation_run_finished,
    valuation_codes_done_for_date,
)


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run 5-step analysis for STAR/ChiNext universe and store in SQLite."
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
        default=10.0,
        help="Seconds to sleep after each stock (default: 10; set 0 to disable)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of stocks to analyze this invocation (excluding skips)",
    )
    args = parser.parse_args()

    db_path = Path(args.db).resolve() if args.db else default_db_path()

    if args.date:
        refresh_date = str(args.date).strip()
    else:
        refresh_date = date.today().isoformat()

    run = get_valuation_run(refresh_date, db_path=db_path)
    if run and run.get("finished_at"):
        print(
            f"Refresh {refresh_date} already completed (finished_at={run['finished_at']}). Exiting.",
            file=sys.stderr,
        )
        sys.exit(0)

    universe = list_star_chinext_symbols(db_path=db_path)
    if not universe:
        print(
            "No STAR/ChiNext symbols in local DB; run scripts/sync_stock_symbols.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    done = valuation_codes_done_for_date(refresh_date, db_path=db_path)
    remaining = [s for s in universe if (s["market"], s["code"]) not in done]
    if args.limit is not None:
        pending = remaining[: max(0, args.limit)]
    else:
        pending = remaining

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ensure_valuation_run_started(
        refresh_date,
        started_at,
        notes="STAR+CHINEXT",
        db_path=db_path,
    )

    if not remaining:
        mark_valuation_run_finished(refresh_date, db_path=db_path)
        print(
            f"refresh_date={refresh_date}: all {len(universe)} symbols already stored; "
            "marked run finished."
        )
        sys.exit(0)

    print(
        f"refresh_date={refresh_date} universe={len(universe)} "
        f"already_done={len(done)} to_process_this_run={len(pending)} db={db_path}"
    )

    conn = sqlite3.connect(str(db_path))
    try:
        init_db(conn)

        ok = 0
        fail = 0
        for i, sym in enumerate(pending, start=1):
            market, code, name = sym["market"], sym["code"], sym["name"]
            board = classify_star_chinext_board(market, code)
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

    done_after = valuation_codes_done_for_date(refresh_date, db_path=db_path)
    still = [s for s in universe if (s["market"], s["code"]) not in done_after]
    if not still:
        mark_valuation_run_finished(refresh_date, db_path=db_path)
        print(f"Finished refresh {refresh_date}. ok={ok} fail={fail} (run closed).")
    else:
        print(
            f"Partial refresh {refresh_date}. ok={ok} fail={fail} "
            f"remaining={len(still)} (run left open for resume)."
        )


if __name__ == "__main__":
    main()
