"""Industry benchmark rows stored in the local SQLite file (``stock_symbols.db``)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from backend.domain.benchmarks.industry_benchmark import IndustryBenchmark
from backend.infrastructure import sqlite_store


def _row_to_vo(row: dict) -> IndustryBenchmark:
    return IndustryBenchmark(
        industry_key=row["industry_key"],
        as_of=row["as_of"],
        roe_median=row["roe_median"],
        roa_median=row["roa_median"],
        gross_margin_median=row["gross_margin_median"],
        debt_ratio_median=row["debt_ratio_median"],
        source_note=row["source_note"],
    )


def get_by_industry_key(
    industry_key: str, db_path: Path | None = None
) -> IndustryBenchmark | None:
    row = sqlite_store.get_industry_benchmark_row(industry_key, db_path=db_path)
    if row is None:
        return None
    return _row_to_vo(row)


def replace_all(
    benchmarks: Sequence[IndustryBenchmark], db_path: Path | None = None
) -> None:
    rows: list[
        tuple[str, str, float | None, float | None, float | None, float | None, str | None]
    ] = [
        (
            b.industry_key,
            b.as_of,
            b.roe_median,
            b.roa_median,
            b.gross_margin_median,
            b.debt_ratio_median,
            b.source_note,
        )
        for b in benchmarks
    ]
    sqlite_store.replace_all_industry_benchmarks(rows, db_path=db_path)


def default_db_path() -> Path:
    return sqlite_store.default_db_path()
