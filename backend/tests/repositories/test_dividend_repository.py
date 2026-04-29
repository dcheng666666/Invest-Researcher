"""Tests for ``backend.repositories.dividend_repository``.

The repository delegates the actual HTTP/AKShare round-trips to the source
layer and is responsible only for: symbol parsing, currency assignment,
fiscal-year resolution, and DataFrame -> ``DividendRecord`` mapping.

Source-level call sites mocked here:
- HK:  ``eastmoney_hk.fetch_dividend_history_hk(code) -> DataFrame``
       Real columns observed: ``财政年度`` (str year), ``分红方案`` (free
       text e.g. "每股派港币0.50元"), ``公告日期`` / ``除净日`` / ``派息日``.
- A:   ``ths_a_share.fetch_dividend_history(code) -> (DataFrame, has_no_dist)``
       Source keeps ``进度`` in ``{"实施", "预案"}`` (drops 预案 when a
       later ``实施`` matches the same ``派息``) and sorts by ``公告日期``.
       The mocked frame only needs ``公告日期``, ``派息``, ``除权除息日``.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.domain.dividends.types import DividendType
from backend.repositories import dividend_repository


# --------------------------------------------------------------------------- #
# A-share path: ths_a_share.fetch_dividend_history
# --------------------------------------------------------------------------- #


def _patch_a_share_dividends(
    monkeypatch: pytest.MonkeyPatch,
    df: pd.DataFrame,
    has_no_distribution: bool = False,
) -> None:
    monkeypatch.setattr(
        dividend_repository.ths_a_share,
        "fetch_dividend_history",
        lambda code: (df, has_no_distribution),
    )


def test_get_history_a_share_maps_payout_per_10_to_per_share_dps_in_cny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real THS shape: 派息 is the cash distributed per 10 shares in CNY,
    # announced on 公告日期 with ex-date 除权除息日.
    df = pd.DataFrame(
        [
            {"公告日期": "2023-07-04", "派息": "3.00", "除权除息日": "2023-07-10"},
            {"公告日期": "2024-07-04", "派息": "3.50", "除权除息日": "2024-07-09"},
        ]
    )
    _patch_a_share_dividends(monkeypatch, df)

    history = dividend_repository.get_history("600519")

    assert history.has_no_distribution is False
    assert history.currency == "CNY"
    assert len(history.records) == 2

    first, second = history.records
    assert first.fiscal_year == "2022"  # July announcement -> previous FY
    assert first.dividend_per_share.amount == pytest.approx(0.30)
    assert first.dividend_per_share.currency == "CNY"
    assert first.dividend_type is DividendType.CASH
    assert first.announcement_date == date(2023, 7, 4)
    assert first.ex_dividend_date == date(2023, 7, 10)
    # THS does not ship a payment date for A-share rows.
    assert first.payment_date is None

    assert second.fiscal_year == "2023"
    assert second.dividend_per_share.amount == pytest.approx(0.35)


def test_get_history_a_share_skips_zero_or_missing_payout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = pd.DataFrame(
        [
            {"公告日期": "2024-07-04", "派息": "0.00", "除权除息日": "2024-07-09"},
            {"公告日期": "2024-08-15", "派息": None, "除权除息日": "2024-08-20"},
            {"公告日期": "2024-09-30", "派息": "1.20", "除权除息日": "2024-10-08"},
        ]
    )
    _patch_a_share_dividends(monkeypatch, df)

    history = dividend_repository.get_history("600519")

    assert len(history.records) == 1
    assert history.records[0].dividend_per_share.amount == pytest.approx(0.12)
    assert history.records[0].fiscal_year == "2024"


def test_get_history_a_share_skips_rows_with_unparseable_announcement_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = pd.DataFrame(
        [
            {"公告日期": "not-a-date", "派息": "2.00", "除权除息日": "2024-07-09"},
            {"公告日期": "2024-07-04", "派息": "2.00", "除权除息日": "2024-07-09"},
        ]
    )
    _patch_a_share_dividends(monkeypatch, df)

    history = dividend_repository.get_history("600519")

    assert len(history.records) == 1
    assert history.records[0].announcement_date == date(2024, 7, 4)


def test_get_history_a_share_propagates_has_no_distribution_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When THS returned only ``不分配`` rows, the source filters them out
    but flips ``has_no_distribution`` so downstream callers can distinguish
    "company actively skipped" from "no upstream data at all"."""
    _patch_a_share_dividends(
        monkeypatch, pd.DataFrame(), has_no_distribution=True
    )

    history = dividend_repository.get_history("000333")

    assert history.is_empty
    assert history.has_no_distribution is True


def test_get_history_a_share_returns_empty_for_empty_dataframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_a_share_dividends(monkeypatch, pd.DataFrame())
    history = dividend_repository.get_history("600519")
    assert history.is_empty
    assert history.has_no_distribution is False


# --------------------------------------------------------------------------- #
# HK path: eastmoney_hk.fetch_dividend_history_hk
# --------------------------------------------------------------------------- #


def _patch_hk_dividends(
    monkeypatch: pytest.MonkeyPatch, df: pd.DataFrame
) -> None:
    monkeypatch.setattr(
        dividend_repository.eastmoney_hk,
        "fetch_dividend_history_hk",
        lambda code: df,
    )


def test_get_history_hk_maps_cash_dividend_in_hkd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real Eastmoney HK shape: 财政年度 verbatim, 分红方案 free-text,
    # plus three optional dates (公告日期 / 除净日 / 派息日).
    df = pd.DataFrame(
        [
            {
                "财政年度": "2023",
                "分红方案": "每股派港币0.50元",
                "公告日期": "2024-03-20",
                "除净日": "2024-06-10",
                "派息日": "2024-07-01",
            },
            {
                "财政年度": "2024",
                "分红方案": "相当于每股派0.30港元",
                "公告日期": "2025-03-22",
                "除净日": "2025-06-12",
                "派息日": "2025-07-03",
            },
        ]
    )
    _patch_hk_dividends(monkeypatch, df)

    history = dividend_repository.get_history("HK00700")

    assert history.has_no_distribution is False
    assert history.currency == "HKD"
    assert len(history.records) == 2

    first, second = history.records
    assert first.fiscal_year == "2023"
    assert first.dividend_per_share.amount == pytest.approx(0.50)
    assert first.dividend_per_share.currency == "HKD"
    assert first.dividend_type is DividendType.CASH
    assert first.announcement_date == date(2024, 3, 20)
    assert first.ex_dividend_date == date(2024, 6, 10)
    assert first.payment_date == date(2024, 7, 1)

    assert second.fiscal_year == "2024"
    assert second.dividend_per_share.amount == pytest.approx(0.30)


def test_get_history_hk_skips_non_cash_plans_and_blank_fiscal_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = pd.DataFrame(
        [
            # Stock split / scrip-only rows: 分红方案 has no 港币 cash phrase.
            {
                "财政年度": "2022",
                "分红方案": "送股 1 股",
                "公告日期": "2023-04-10",
                "除净日": "2023-06-01",
                "派息日": "2023-06-20",
            },
            # Blank fiscal_year is dropped even when the plan is parseable.
            {
                "财政年度": "",
                "分红方案": "每股派港币0.20元",
                "公告日期": "2023-09-15",
                "除净日": "2023-10-10",
                "派息日": "2023-10-25",
            },
            # Valid cash dividend.
            {
                "财政年度": "2023",
                "分红方案": "每股派港币0.40元",
                "公告日期": "2024-03-20",
                "除净日": "2024-06-10",
                "派息日": "2024-07-01",
            },
        ]
    )
    _patch_hk_dividends(monkeypatch, df)

    history = dividend_repository.get_history("HK00700")

    assert len(history.records) == 1
    assert history.records[0].fiscal_year == "2023"
    assert history.records[0].dividend_per_share.amount == pytest.approx(0.40)


def test_get_history_hk_returns_empty_for_empty_dataframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_hk_dividends(monkeypatch, pd.DataFrame())
    history = dividend_repository.get_history("HK00700")
    assert history.is_empty
    assert history.has_no_distribution is False


def test_get_history_hk_tolerates_missing_optional_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = pd.DataFrame(
        [
            {
                "财政年度": "2023",
                "分红方案": "每股派港币0.50元",
                "公告日期": None,
                "除净日": None,
                "派息日": None,
            }
        ]
    )
    _patch_hk_dividends(monkeypatch, df)

    history = dividend_repository.get_history("HK00700")

    assert len(history.records) == 1
    record = history.records[0]
    assert record.announcement_date is None
    assert record.ex_dividend_date is None
    assert record.payment_date is None
    assert record.dividend_per_share.amount == pytest.approx(0.50)
