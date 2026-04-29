#!/usr/bin/env python3
"""Fetch A-share and HK symbols from akshare and write local SQLite for search."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from backend.infrastructure.sources.stock_lists import (
    a_share_market_for_code,
    fetch_a_share_code_name_df,
    fetch_hk_stock_list_df,
)
from backend.infrastructure.sqlite_store import default_db_path, replace_all_symbols


def main() -> None:
    t0 = time.perf_counter()
    a_df = fetch_a_share_code_name_df()
    hk_df = fetch_hk_stock_list_df()
    rows: list[tuple[str, str, str]] = []
    skipped_bse = 0
    for _, r in a_df.iterrows():
        code = str(r["code"]).strip()
        name = str(r["name"]).strip()
        if not code or not name:
            continue
        # Beijing Stock Exchange (codes starting with 8/4) is not supported yet.
        if code.startswith(("8", "4")):
            skipped_bse += 1
            continue
        rows.append((a_share_market_for_code(code), code, name))
    for _, r in hk_df.iterrows():
        code = str(r["code"]).strip()
        name = str(r["name"]).strip()
        if not code or not name:
            continue
        rows.append(("HK", code, name))
    path = default_db_path()
    replace_all_symbols(rows, db_path=path)
    elapsed = time.perf_counter() - t0
    print(
        f"Synced {len(rows)} symbols (A-share source rows={len(a_df)}, "
        f"BSE skipped={skipped_bse}, HK={len(hk_df)}) -> {path} in {elapsed:.1f}s"
    )


if __name__ == "__main__":
    main()
