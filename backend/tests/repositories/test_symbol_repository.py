"""Tests for ``backend.repositories.symbol_repository``.

Exercises the SQLite-backed lookup/search/sync flow against a temporary DB
and pins the A-share market-bucket inference (SH / SZ / OTHER) used as the
DB primary-key partition.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.infrastructure import sqlite_store
from backend.repositories import symbol_repository
from backend.repositories.symbol_repository import _db_market_for_a_share


# --------------------------------------------------------------------------- #
# _db_market_for_a_share
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("600519", "SH"),
        ("601398", "SH"),
        ("000333", "SZ"),
        ("002475", "SZ"),
        ("300750", "SZ"),
        # BSE listings (8/4) are not currently supported -> bucketed as OTHER.
        ("830799", "OTHER"),
        ("430047", "OTHER"),
    ],
)
def test_db_market_for_a_share_partitions_by_leading_digit(
    code: str, expected: str
) -> None:
    assert _db_market_for_a_share(code) == expected


# --------------------------------------------------------------------------- #
# initialize / replace_all / search / lookup roundtrip
# --------------------------------------------------------------------------- #


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "stock_symbols.db"


def test_initialize_creates_empty_db_with_expected_schema(tmp_db: Path) -> None:
    assert not tmp_db.exists()
    symbol_repository.initialize(db_path=tmp_db)
    assert tmp_db.is_file()
    # Schema is ready before any rows are inserted: search returns []
    # rather than crashing.
    assert symbol_repository.search("anything", db_path=tmp_db) == []


def test_replace_all_then_lookup_returns_matching_row(tmp_db: Path) -> None:
    symbol_repository.replace_all(
        [
            ("SH", "600519", "贵州茅台"),
            ("SZ", "000333", "美的集团"),
            ("HK", "00700", "腾讯控股"),
        ],
        db_path=tmp_db,
    )

    a_row = symbol_repository.lookup("600519", db_path=tmp_db)
    assert a_row == {"code": "600519", "name": "贵州茅台", "market": "SH"}

    sz_row = symbol_repository.lookup("SZ000333", db_path=tmp_db)
    assert sz_row == {"code": "000333", "name": "美的集团", "market": "SZ"}

    hk_row = symbol_repository.lookup("HK00700", db_path=tmp_db)
    assert hk_row == {"code": "00700", "name": "腾讯控股", "market": "HK"}


def test_lookup_returns_none_when_symbol_missing(tmp_db: Path) -> None:
    symbol_repository.replace_all(
        [("SH", "600519", "贵州茅台")], db_path=tmp_db
    )
    assert symbol_repository.lookup("999999", db_path=tmp_db) is None


def test_search_matches_by_name_or_code_substring(tmp_db: Path) -> None:
    symbol_repository.replace_all(
        [
            ("SH", "600519", "贵州茅台"),
            ("SH", "601398", "工商银行"),
            ("SZ", "000333", "美的集团"),
        ],
        db_path=tmp_db,
    )

    by_name = symbol_repository.search("茅台", db_path=tmp_db)
    assert by_name == [{"code": "600519", "name": "贵州茅台", "market": "SH"}]

    by_code = symbol_repository.search("0003", db_path=tmp_db)
    assert by_code == [{"code": "000333", "name": "美的集团", "market": "SZ"}]


def test_replace_all_dedupes_by_market_code_keeping_last(tmp_db: Path) -> None:
    """``replace_all`` performs an in-memory dedup before insert.

    The second tuple wins because the dict-overwrite happens left-to-right.
    """
    symbol_repository.replace_all(
        [
            ("SH", "600519", "old name"),
            ("SH", "600519", "贵州茅台"),
        ],
        db_path=tmp_db,
    )
    row = symbol_repository.lookup("600519", db_path=tmp_db)
    assert row == {"code": "600519", "name": "贵州茅台", "market": "SH"}


def test_display_name_returns_db_name_when_present(monkeypatch, tmp_db: Path) -> None:
    """``display_name`` has no ``db_path`` parameter, so we redirect the
    sqlite_store default at the module level for an isolated test.
    """
    monkeypatch.setattr(sqlite_store, "DEFAULT_DB_PATH", tmp_db)
    symbol_repository.replace_all([("SH", "600519", "贵州茅台")])

    assert symbol_repository.display_name("600519") == "贵州茅台"
    # When the symbol is unknown, ``display_name`` echoes the raw input back.
    assert symbol_repository.display_name("999999") == "999999"
