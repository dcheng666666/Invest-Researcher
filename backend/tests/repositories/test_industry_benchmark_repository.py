"""Tests for ``backend.repositories.industry_benchmark_repository``."""

from __future__ import annotations

from pathlib import Path

from backend.domain.benchmarks.industry_benchmark import IndustryBenchmark
from backend.repositories import industry_benchmark_repository, symbol_repository


def test_initialize_via_symbol_store_creates_benchmarks_table(tmp_path: Path) -> None:
    db = tmp_path / "stock_symbols.db"
    symbol_repository.initialize(db_path=db)
    assert industry_benchmark_repository.get_by_industry_key("any", db_path=db) is None


def test_replace_all_then_get_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "stock_symbols.db"
    symbol_repository.initialize(db_path=db)
    b = IndustryBenchmark(
        industry_key="白酒",
        as_of="2024-12-31",
        roe_median=0.18,
        roa_median=0.12,
        gross_margin_median=0.70,
        debt_ratio_median=0.32,
        source_note="unit test",
    )
    industry_benchmark_repository.replace_all([b], db_path=db)
    got = industry_benchmark_repository.get_by_industry_key("白酒", db_path=db)
    assert got == b
    assert industry_benchmark_repository.get_by_industry_key(" 白酒 ", db_path=db) == b
    assert industry_benchmark_repository.get_by_industry_key("白酒业", db_path=db) is None


def test_replace_all_clears_previous_rows(tmp_path: Path) -> None:
    db = tmp_path / "stock_symbols.db"
    symbol_repository.initialize(db_path=db)
    industry_benchmark_repository.replace_all(
        [
            IndustryBenchmark(
                industry_key="A",
                as_of="2024-01-01",
                source_note=None,
            )
        ],
        db_path=db,
    )
    industry_benchmark_repository.replace_all(
        [
            IndustryBenchmark(
                industry_key="B",
                as_of="2024-01-01",
                source_note=None,
            )
        ],
        db_path=db,
    )
    assert industry_benchmark_repository.get_by_industry_key("A", db_path=db) is None
    assert industry_benchmark_repository.get_by_industry_key("B", db_path=db) is not None
