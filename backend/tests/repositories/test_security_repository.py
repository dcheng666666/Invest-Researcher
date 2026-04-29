"""Tests for ``backend.repositories.security_repository``.

The repository assembles a ``Security`` aggregate from upstream profile +
quote dicts and an optional monthly market-cap frame. We mock at the
source-module boundary so the upstream-call shape stays an explicit part
of the contract:

- A-share profile/quote: ``xueqiu.fetch_stock_info_a(code) -> dict``
       Real keys consumed: ``股票简称``, ``行业``, ``上市日期``, ``最新``,
       ``总市值`` (yuan), ``总股本`` (shares).
- HK profile/quote: ``eastmoney_hk.fetch_stock_info_hk(code) -> dict``
       Same set of keys, populated by ``hk_latest_shares_and_mcap``.
- Market-cap frame: ``load_market_cap_frame(market, code, ...) -> DataFrame``
       Returns columns ``date`` (Timestamp) and ``market_cap`` (亿 unit,
       i.e. 1e8 of the market currency). The repository converts to raw
       yuan / HKD by multiplying by 1e8.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.domain.stocks.exchange import HKEX, SSE, SZSE
from backend.domain.stocks.market import Market
from backend.repositories import security_repository


# --------------------------------------------------------------------------- #
# get_security: A-share path (Xueqiu)
# --------------------------------------------------------------------------- #


def test_get_security_a_share_assembles_aggregate_from_xueqiu_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = {
        "股票简称": "贵州茅台",
        "行业": "白酒",
        "上市日期": "2001-08-27",
        # 最新 is the latest spot price in CNY; 总市值/总股本 are absolute
        # (not 亿/万) per Xueqiu's spot endpoint.
        "最新": 1680.5,
        "总市值": 2_111_000_000_000.0,
        "总股本": 1_256_197_800.0,
    }
    monkeypatch.setattr(
        security_repository.xueqiu, "fetch_stock_info_a", lambda code: info
    )

    sec = security_repository.get_security("600519")

    assert sec.symbol.code == "600519"
    assert sec.symbol.market is Market.A
    assert sec.exchange is SSE
    assert sec.name == "贵州茅台"
    assert sec.profile.list_date == "2001-08-27"
    assert sec.industry == "白酒"
    assert sec.company.region == "CN"

    snap = sec.latest_snapshot
    assert snap is not None
    assert snap.symbol == sec.symbol
    assert snap.current_price == pytest.approx(1680.5)
    assert snap.market_cap == pytest.approx(2_111_000_000_000.0)
    assert snap.total_shares == pytest.approx(1_256_197_800.0)


def test_get_security_a_share_routes_szse_for_leading_zero_or_three(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security_repository.xueqiu,
        "fetch_stock_info_a",
        lambda code: {"股票简称": "美的集团", "最新": 70.0},
    )
    sec = security_repository.get_security("000333")
    assert sec.exchange is SZSE
    assert sec.symbol.market is Market.A


# --------------------------------------------------------------------------- #
# get_security: HK path (Eastmoney HK)
# --------------------------------------------------------------------------- #


def test_get_security_hk_assembles_aggregate_from_eastmoney_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = {
        "股票简称": "腾讯控股",
        "行业": "软件服务",
        "总股本": 9_300_000_000.0,
        "总市值": 3_000_000_000_000.0,
        "最新": 322.58,
    }
    monkeypatch.setattr(
        security_repository.eastmoney_hk,
        "fetch_stock_info_hk",
        lambda code: info,
    )

    sec = security_repository.get_security("HK00700")

    assert sec.symbol.code == "00700"
    assert sec.symbol.market is Market.HK
    assert sec.exchange is HKEX
    assert sec.currency == "HKD"
    assert sec.name == "腾讯控股"
    assert sec.industry == "软件服务"
    assert sec.company.region == "HK"
    assert sec.profile.list_date is None  # HK feed does not surface 上市日期

    snap = sec.latest_snapshot
    assert snap is not None
    assert snap.current_price == pytest.approx(322.58)
    assert snap.market_cap == pytest.approx(3_000_000_000_000.0)
    assert snap.total_shares == pytest.approx(9_300_000_000.0)


# --------------------------------------------------------------------------- #
# get_security: derived current_price fallback
# --------------------------------------------------------------------------- #


def test_get_security_derives_current_price_from_mcap_and_shares_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = {
        "股票简称": "腾讯控股",
        "总股本": 9_300_000_000.0,
        "总市值": 3_000_000_000_000.0,
        # 最新 absent; repository should derive ``mcap / shares``.
    }
    monkeypatch.setattr(
        security_repository.eastmoney_hk,
        "fetch_stock_info_hk",
        lambda code: info,
    )

    sec = security_repository.get_security("HK00700")

    assert sec.latest_snapshot is not None
    assert sec.latest_snapshot.current_price == pytest.approx(
        3_000_000_000_000.0 / 9_300_000_000.0
    )


def test_get_security_falls_back_to_symbol_code_when_name_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When upstream fails to provide ``股票简称``, ``Profile.name`` falls
    back to the canonical symbol code; the snapshot still composes from
    whatever quote data is available.
    """
    monkeypatch.setattr(
        security_repository.xueqiu,
        "fetch_stock_info_a",
        lambda code: {},
    )
    sec = security_repository.get_security("600519")
    assert sec.name == "600519"
    assert sec.latest_snapshot is not None
    assert sec.latest_snapshot.current_price is None
    assert sec.latest_snapshot.market_cap is None


# --------------------------------------------------------------------------- #
# get_market_cap_history
# --------------------------------------------------------------------------- #


def _mcap_frame(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """Build a ``date`` / ``market_cap`` (亿) frame in the shape the source
    layer hands back, ready for ``monthly_mcap_rows``.
    """
    return pd.DataFrame(
        {
            "date": pd.to_datetime([d for d, _ in rows]),
            "market_cap": [v for _, v in rows],
        }
    )


def test_get_market_cap_history_a_share_converts_yi_to_raw_yuan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _mcap_frame(
        [
            ("2024-01-31", 21000.0),  # 21000 亿 = 2.1e12 yuan
            ("2024-02-29", 21500.0),
            ("2024-03-31", 22000.0),
        ]
    )

    def fake_loader(market, code, window_years, period="monthly"):
        assert market is Market.A
        assert code == "600519"
        assert period == "monthly"
        return frame

    monkeypatch.setattr(
        security_repository, "load_market_cap_frame", fake_loader
    )

    history = security_repository.get_market_cap_history("600519")

    assert history.as_pairs() == [
        ("2024-01", 21000.0 * 1e8),
        ("2024-02", 21500.0 * 1e8),
        ("2024-03", 22000.0 * 1e8),
    ]


def test_get_market_cap_history_hk_routes_through_hk_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _mcap_frame(
        [
            ("2024-01-31", 28000.0),  # 亿港元 -> raw HKD
            ("2024-02-29", 29000.0),
        ]
    )
    captured: dict = {}

    def fake_loader(market, code, window_years, period="monthly"):
        captured["market"] = market
        captured["code"] = code
        captured["window_years"] = window_years
        return frame

    monkeypatch.setattr(
        security_repository, "load_market_cap_frame", fake_loader
    )

    history = security_repository.get_market_cap_history(
        "HK00700", window_years=3
    )

    assert captured == {"market": Market.HK, "code": "00700", "window_years": 3}
    assert history.as_pairs() == [
        ("2024-01", 28000.0 * 1e8),
        ("2024-02", 29000.0 * 1e8),
    ]


def test_get_market_cap_history_returns_empty_when_loader_yields_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security_repository,
        "load_market_cap_frame",
        lambda *args, **kwargs: pd.DataFrame(),
    )

    history = security_repository.get_market_cap_history("600519")

    assert history.is_empty()
    assert history.as_pairs() == []


# --------------------------------------------------------------------------- #
# load_security_with_history (composite loader)
# --------------------------------------------------------------------------- #


def test_load_security_with_history_attaches_history_to_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security_repository.xueqiu,
        "fetch_stock_info_a",
        lambda code: {
            "股票简称": "贵州茅台",
            "最新": 1680.5,
            "总市值": 2_111_000_000_000.0,
            "总股本": 1_256_197_800.0,
        },
    )
    monkeypatch.setattr(
        security_repository,
        "load_market_cap_frame",
        lambda *args, **kwargs: _mcap_frame(
            [
                ("2024-01-31", 21000.0),
                ("2024-02-29", 21500.0),
            ]
        ),
    )

    sec = security_repository.load_security_with_history("600519")

    assert sec.name == "贵州茅台"
    assert sec.latest_snapshot is not None
    assert not sec.market_cap_history.is_empty()
    assert sec.market_cap_history.as_pairs() == [
        ("2024-01", 21000.0 * 1e8),
        ("2024-02", 21500.0 * 1e8),
    ]
