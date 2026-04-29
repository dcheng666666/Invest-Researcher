"""Tests for THS A-share dividend fetch filtering (实施 + 预案)."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.infrastructure.sources import ths_a_share


def test_fetch_dividend_history_keeps_standalone_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = pd.DataFrame(
        [
            {
                "公告日期": "2026-03-26",
                "送股": 0,
                "转增": 0,
                "派息": 12.5228,
                "进度": "预案",
                "除权除息日": None,
                "股权登记日": None,
                "红股上市日": None,
            },
            {
                "公告日期": "2025-07-07",
                "送股": 0,
                "转增": 0,
                "派息": 8.9852,
                "进度": "实施",
                "除权除息日": "2025-07-11",
                "股权登记日": "2025-07-10",
                "红股上市日": None,
            },
        ]
    )

    def _fake_cached_call(_key: str, _ttl: object, _func: object, **kwargs: object) -> pd.DataFrame:
        return sample

    monkeypatch.setattr(ths_a_share, "cached_call", _fake_cached_call)

    df, has_no_distribution = ths_a_share.fetch_dividend_history("688111")

    assert has_no_distribution is False
    assert len(df) == 2
    assert set(df["进度"].tolist()) == {"预案", "实施"}


def test_fetch_dividend_history_drops_proposal_when_followed_by_matching_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = pd.DataFrame(
        [
            {
                "公告日期": "2026-03-01",
                "送股": 0,
                "转增": 0,
                "派息": 10.0,
                "进度": "预案",
                "除权除息日": None,
                "股权登记日": None,
                "红股上市日": None,
            },
            {
                "公告日期": "2026-05-01",
                "送股": 0,
                "转增": 0,
                "派息": 10.0,
                "进度": "实施",
                "除权除息日": "2026-05-10",
                "股权登记日": "2026-05-09",
                "红股上市日": None,
            },
        ]
    )

    def _fake_cached_call(_key: str, _ttl: object, _func: object, **kwargs: object) -> pd.DataFrame:
        return sample

    monkeypatch.setattr(ths_a_share, "cached_call", _fake_cached_call)

    df, _ = ths_a_share.fetch_dividend_history("000001")

    assert len(df) == 1
    assert df.iloc[0]["进度"] == "实施"
    assert float(df.iloc[0]["派息"]) == pytest.approx(10.0)


def test_fetch_dividend_history_has_no_distribution_all_rows_reject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = pd.DataFrame(
        [
            {
                "公告日期": "2025-04-01",
                "送股": 0,
                "转增": 0,
                "派息": 0.0,
                "进度": "不分配",
                "除权除息日": None,
                "股权登记日": None,
                "红股上市日": None,
            },
        ]
    )

    def _fake_cached_call(_key: str, _ttl: object, _func: object, **kwargs: object) -> pd.DataFrame:
        return sample

    monkeypatch.setattr(ths_a_share, "cached_call", _fake_cached_call)

    df, has_no_distribution = ths_a_share.fetch_dividend_history("000001")

    assert has_no_distribution is True
    assert df.empty
