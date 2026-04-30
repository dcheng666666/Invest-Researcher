"""CLI: run rule analysis and write results to an .xlsx file (no HTTP server)."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from backend.api.excel_export import export_rule_analysis_to_path
from backend.application.analysis import service as analysis_service
from backend.infrastructure.parsers import DEFAULT_WINDOW_YEARS


def main() -> None:
    parser = argparse.ArgumentParser(description="Export stock rule analysis to Excel.")
    parser.add_argument("code", help="Stock code, e.g. 600519 or HK00700")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output .xlsx path (default: exports/<code>_<timestamp>.xlsx)",
    )
    parser.add_argument(
        "--window-years",
        type=int,
        default=DEFAULT_WINDOW_YEARS,
        metavar="N",
        help=f"Rolling financial / market-cap window (default: {DEFAULT_WINDOW_YEARS}, range 3–20)",
    )
    args = parser.parse_args()
    code = args.code.strip()
    wy = args.window_years
    if wy < 3 or wy > 20:
        print("window-years must be between 3 and 20", file=sys.stderr)
        sys.exit(2)
    ctx = analysis_service.build_context(code, window_years=wy)
    if ctx is None:
        print("No financial data for code:", code, file=sys.stderr)
        sys.exit(1)
    name = analysis_service.stock_display_name(code)
    results, errors, scores = analysis_service.run_steps(ctx)
    out_path = (
        Path(args.output)
        if args.output
        else Path("exports") / f"{code.replace('.', '_')}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    )
    export_rule_analysis_to_path(out_path, code, name, results, errors, scores)
    print(out_path.resolve())


if __name__ == "__main__":
    main()
