#!/usr/bin/env python3
"""Load illustrative industry benchmark rows into local SQLite.

Keys must match upstream ``行业`` strings (e.g. from Xueqiu / Eastmoney) if you
intend ``get_by_industry_key(security.industry)`` to hit. Replace the sample
rows with your own sourced aggregates before relying on scores.

Usage::

    uv run python scripts/seed_industry_benchmarks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.benchmarks.industry_benchmark import IndustryBenchmark
from backend.infrastructure.sqlite_store import default_db_path, initialize_store
from backend.repositories import industry_benchmark_repository

_SEED_NOTE = (
    "illustrative medians for seeding only — replace with your sourced aggregates"
)


def _row(
    industry_key: str,
    *,
    roe: float,
    roa: float,
    gross_margin: float | None,
    debt: float,
) -> IndustryBenchmark:
    return IndustryBenchmark(
        industry_key=industry_key,
        as_of="2024-12-31",
        roe_median=roe,
        roa_median=roa,
        gross_margin_median=gross_margin,
        debt_ratio_median=debt,
        source_note=_SEED_NOTE,
    )


# Common A-share style labels (申万一级 / 东财板块口径为主) + 部分细分/港股常见写法。
# Numeric fields are order-of-magnitude placeholders, not computed from market data.
_SAMPLE: tuple[IndustryBenchmark, ...] = (
    # --- Finance (high balance-sheet leverage; GM often not comparable) ---
    _row("银行", roe=0.10, roa=0.008, gross_margin=None, debt=0.91),
    _row("非银金融", roe=0.08, roa=0.018, gross_margin=None, debt=0.85),
    _row("证券", roe=0.06, roa=0.022, gross_margin=None, debt=0.72),
    _row("保险", roe=0.11, roa=0.009, gross_margin=None, debt=0.89),
    # --- Real estate & construction ---
    _row("房地产", roe=0.05, roa=0.018, gross_margin=0.20, debt=0.76),
    _row("建筑装饰", roe=0.08, roa=0.021, gross_margin=0.12, debt=0.74),
    _row("建筑材料", roe=0.07, roa=0.038, gross_margin=0.22, debt=0.48),
    # --- Cyclicals & materials ---
    _row("煤炭", roe=0.12, roa=0.055, gross_margin=0.34, debt=0.54),
    _row("石油石化", roe=0.08, roa=0.042, gross_margin=0.18, debt=0.52),
    _row("有色金属", roe=0.10, roa=0.048, gross_margin=0.12, debt=0.52),
    _row("钢铁", roe=0.06, roa=0.032, gross_margin=0.09, debt=0.58),
    _row("基础化工", roe=0.09, roa=0.048, gross_margin=0.19, debt=0.48),
    # --- Manufacturing ---
    _row("机械设备", roe=0.09, roa=0.042, gross_margin=0.23, debt=0.51),
    _row("电力设备", roe=0.11, roa=0.048, gross_margin=0.22, debt=0.55),
    _row("汽车", roe=0.08, roa=0.038, gross_margin=0.16, debt=0.58),
    _row("家用电器", roe=0.14, roa=0.058, gross_margin=0.26, debt=0.61),
    _row("国防军工", roe=0.06, roa=0.028, gross_margin=0.22, debt=0.50),
    _row("轻工制造", roe=0.09, roa=0.048, gross_margin=0.24, debt=0.45),
    # --- TMT ---
    _row("电子", roe=0.10, roa=0.052, gross_margin=0.21, debt=0.44),
    _row("计算机", roe=0.07, roa=0.038, gross_margin=0.36, debt=0.38),
    _row("通信", roe=0.06, roa=0.032, gross_margin=0.28, debt=0.45),
    _row("传媒", roe=0.05, roa=0.022, gross_margin=0.32, debt=0.41),
    _row("软件服务", roe=0.08, roa=0.048, gross_margin=0.46, debt=0.35),
    _row("互联网", roe=0.09, roa=0.055, gross_margin=0.42, debt=0.36),
    # --- Consumer & healthcare ---
    _row("食品饮料", roe=0.15, roa=0.098, gross_margin=0.42, debt=0.35),
    _row("白酒", roe=0.20, roa=0.14, gross_margin=0.76, debt=0.30),
    _row("医药生物", roe=0.12, roa=0.068, gross_margin=0.44, debt=0.40),
    _row("纺织服饰", roe=0.07, roa=0.038, gross_margin=0.28, debt=0.42),
    _row("商贸零售", roe=0.05, roa=0.022, gross_margin=0.20, debt=0.64),
    _row("社会服务", roe=0.05, roa=0.028, gross_margin=0.36, debt=0.42),
    _row("美容护理", roe=0.11, roa=0.058, gross_margin=0.46, debt=0.36),
    # --- Utilities & infra ---
    _row("公用事业", roe=0.08, roa=0.032, gross_margin=0.20, debt=0.61),
    _row("交通运输", roe=0.09, roa=0.042, gross_margin=0.15, debt=0.55),
    _row("环保", roe=0.07, roa=0.032, gross_margin=0.28, debt=0.54),
    # --- Agri & misc ---
    _row("农林牧渔", roe=0.08, roa=0.042, gross_margin=0.17, debt=0.50),
    _row("综合", roe=0.05, roa=0.022, gross_margin=0.15, debt=0.55),
)


def main() -> None:
    path = default_db_path()
    initialize_store(path)
    industry_benchmark_repository.replace_all(_SAMPLE, db_path=path)
    print(f"Seeded {len(_SAMPLE)} industry_benchmarks rows into {path}")


if __name__ == "__main__":
    main()
