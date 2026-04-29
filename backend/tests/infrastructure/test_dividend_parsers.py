"""Tests for dividend-related upstream-format parsers."""

from __future__ import annotations

from datetime import date

import pytest

from backend.infrastructure.parsers import (
    parse_hk_dividend_per_share,
    ths_fiscal_year_from_announcement,
)


# --------------------------------------------------------------------------- #
# parse_hk_dividend_per_share
# --------------------------------------------------------------------------- #


def test_parse_hk_dividend_per_share_extracts_hkd_amount() -> None:
    assert parse_hk_dividend_per_share("每股派港币0.50元") == 0.5
    assert parse_hk_dividend_per_share("相当于每股派0.30港元") == 0.3


def test_parse_hk_dividend_per_share_returns_none_for_unmatched_or_empty() -> None:
    assert parse_hk_dividend_per_share("") is None
    assert parse_hk_dividend_per_share("送股 1 股") is None
    assert parse_hk_dividend_per_share("派发美元股息 0.10 美元") is None


# --------------------------------------------------------------------------- #
# ths_fiscal_year_from_announcement
#
# These cases are pinned to real implementation announcements observed in
# THS data so the heuristic stays grounded in observed company behaviour.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "announce,expected_fy,case",
    [
        # Final dividends (上一财年末期), implementation lands H1 of next year.
        (date(2024, 7, 4), "2023", "招行 FY2023 final"),
        (date(2025, 7, 4), "2024", "招行 FY2024 final"),
        (date(2024, 7, 9), "2023", "工行 FY2023 final"),
        (date(2024, 6, 12), "2023", "茅台 FY2023 final"),
        (date(2024, 6, 6), "2023", "平安银行 FY2023 final"),
        (date(2024, 7, 19), "2023", "中国平安 FY2023 final"),
        (date(2025, 3, 29), "2024", "工行 FY2024 final, early announce / late ex-date"),
        # Current-FY interim / Q3 / year-end specials.
        (date(2024, 9, 26), "2024", "平安银行 FY2024 interim"),
        (date(2024, 10, 11), "2024", "中国平安 FY2024 interim"),
        (date(2024, 12, 31), "2024", "工行 FY2024 interim"),
        (date(2024, 12, 14), "2024", "茅台 FY2024 special"),
        # Regression: late-August implementations belong to the CURRENT FY.
        (date(2019, 8, 29), "2019", "中国平安 FY2019 interim"),
        (date(2018, 8, 30), "2018", "中国平安 FY2018 interim"),
        (date(2017, 8, 26), "2017", "中国平安 FY2017 interim"),
        (date(2016, 8, 27), "2016", "中国平安 FY2016 interim"),
        # FY interim / special whose implementation slips into early next year.
        (date(2026, 1, 10), "2025", "招行 FY2025 interim implemented next January"),
        # Boundary cases at month=7 and month=8.
        (date(2023, 7, 31), "2022", "month=7 boundary -> previous FY"),
        (date(2023, 8, 1), "2023", "month=8 boundary -> current FY"),
    ],
)
def test_ths_fiscal_year_from_announcement(
    announce: date, expected_fy: str, case: str
) -> None:
    assert ths_fiscal_year_from_announcement(announce) == expected_fy, case
