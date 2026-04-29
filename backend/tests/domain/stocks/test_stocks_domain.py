from __future__ import annotations

from datetime import datetime

import pytest

import backend.domain.stocks as stocks
from backend.domain.stocks import (
    HKEX,
    SSE,
    SZSE,
    Company,
    Market,
    MarketCapHistory,
    MarketCapPoint,
    Profile,
    Security,
    StockSnapshot,
    Symbol,
    exchange_for_symbol,
)
from backend.infrastructure.symbol_resolver import parse_symbol


def test_package_public_api_exports() -> None:
    expected = {
        "Company",
        "Exchange",
        "HKEX",
        "Market",
        "MarketCapHistory",
        "MarketCapPoint",
        "SSE",
        "SZSE",
        "Profile",
        "Security",
        "StockSnapshot",
        "Symbol",
        "exchange_for_symbol",
    }
    assert set(stocks.__all__) == expected
    for name in expected:
        assert hasattr(stocks, name)


def test_market_default_currency_and_region() -> None:
    assert Market.A.default_currency == "CNY"
    assert Market.A.default_region == "CN"
    assert Market.HK.default_currency == "HKD"
    assert Market.HK.default_region == "HK"


def test_symbol_string_representation() -> None:
    assert str(Symbol(code="600519", market=Market.A)) == "600519.A"
    assert str(Symbol(code="00700", market=Market.HK)) == "00700.HK"


def test_exchange_for_symbol_resolves_by_market_and_code_head() -> None:
    assert exchange_for_symbol(Symbol(code="00700", market=Market.HK)) is HKEX
    assert exchange_for_symbol(Symbol(code="600519", market=Market.A)) is SSE
    assert exchange_for_symbol(Symbol(code="000001", market=Market.A)) is SZSE
    assert exchange_for_symbol(Symbol(code="300750", market=Market.A)) is SZSE
    assert exchange_for_symbol(Symbol(code="830799", market=Market.A)) is SSE


def test_security_properties_and_latest_snapshot() -> None:
    symbol = Symbol(code="00700", market=Market.HK)
    snapshot = StockSnapshot(
        symbol=symbol,
        current_price=320.0,
        market_cap=3_000_000_000_000.0,
        total_shares=9_300_000_000.0,
        as_of=datetime(2026, 1, 2, 16, 0, 0),
    )
    security = Security(
        symbol=symbol,
        exchange=HKEX,
        profile=Profile(name="Tencent"),
        company=Company(legal_name="Tencent Holdings Ltd.", industry="Internet"),
        latest_snapshot=snapshot,
    )

    assert security.market is Market.HK
    assert security.currency == "HKD"
    assert security.name == "Tencent"
    assert security.industry == "Internet"
    assert security.latest_snapshot is snapshot


def test_security_latest_snapshot_defaults_to_none() -> None:
    security = Security(
        symbol=Symbol(code="600519", market=Market.A),
        exchange=SSE,
        profile=Profile(name="Kweichow Moutai"),
    )
    assert security.latest_snapshot is None


def test_security_rejects_snapshot_with_mismatched_symbol() -> None:
    symbol = Symbol(code="600519", market=Market.A)
    wrong_snapshot = StockSnapshot(
        symbol=Symbol(code="00700", market=Market.HK),
        current_price=300.0,
        market_cap=3_000_000_000_000.0,
        total_shares=9_300_000_000.0,
        as_of=datetime(2026, 1, 3, 16, 0, 0),
    )
    with pytest.raises(ValueError, match="Snapshot symbol"):
        Security(
            symbol=symbol,
            exchange=SSE,
            profile=Profile(name="Kweichow Moutai"),
            latest_snapshot=wrong_snapshot,
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("600519", Symbol(code="600519", market=Market.A)),
        ("SH600519", Symbol(code="600519", market=Market.A)),
        ("SZ000333", Symbol(code="000333", market=Market.A)),
        ("700", Symbol(code="00700", market=Market.HK)),
        ("HK00700", Symbol(code="00700", market=Market.HK)),
        ("00700.HK", Symbol(code="00700", market=Market.HK)),
    ],
)
def test_parse_symbol_returns_symbol_value_object(
    raw: str, expected: Symbol
) -> None:
    assert parse_symbol(raw) == expected


def test_market_cap_history_from_pairs_sorts_and_dedupes() -> None:
    history = MarketCapHistory.from_pairs(
        [
            ("2024-03", 105e8),
            ("2024-01", 100e8),
            ("2024-02", 110e8),
            ("2024-02", 115e8),  # duplicate period: last write wins
        ]
    )
    assert history.as_pairs() == [
        ("2024-01", 100e8),
        ("2024-02", 115e8),
        ("2024-03", 105e8),
    ]
    assert history.points[0] == MarketCapPoint(period="2024-01", market_cap=100e8)


def test_market_cap_history_from_pairs_drops_nan_and_invalid() -> None:
    history = MarketCapHistory.from_pairs(
        [
            ("2024-01", 100e8),
            ("", 999e8),  # empty period dropped
            ("2024-02", float("nan")),  # NaN dropped
            ("2024-03", "not-a-number"),  # type-coercion failure dropped
            ("2024-04", 120e8),
        ]
    )
    assert [p.period for p in history.points] == ["2024-01", "2024-04"]


def test_market_cap_history_default_is_empty() -> None:
    history = MarketCapHistory()
    assert history.is_empty()
    assert history.as_pairs() == []


def test_security_with_market_cap_history_replaces_and_is_immutable() -> None:
    symbol = Symbol(code="600519", market=Market.A)
    security = Security(
        symbol=symbol,
        exchange=SSE,
        profile=Profile(name="Kweichow Moutai"),
    )
    history = MarketCapHistory.from_pairs([("2024-01", 100e8), ("2024-02", 110e8)])

    updated = security.with_market_cap_history(history)

    assert security.market_cap_history.is_empty()
    assert updated.market_cap_history is history
    assert updated.market_cap_history.as_pairs() == [
        ("2024-01", 100e8),
        ("2024-02", 110e8),
    ]
