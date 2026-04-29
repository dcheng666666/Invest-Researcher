"""Tests for HK F10 main-indicator income YTD -> discrete quarter deaccumulation."""

from __future__ import annotations

from datetime import date

import pytest

from backend.infrastructure.sources.hk_f10_income_deaccum import (
    deaccumulate_hk_main_indicator_income_rows,
    deaccumulate_hk_ytd_scalars_aligned,
    infer_hk_main_indicator_fiscal_year_end_month,
)


def test_infer_march_fy_from_mar_jun_drop() -> None:
    ds = [
        date(2024, 3, 31),
        date(2024, 6, 30),
    ]
    vs = [800.0, 200.0]
    assert infer_hk_main_indicator_fiscal_year_end_month(ds, vs) == 3


def test_infer_december_fy_from_dec_mar_drop() -> None:
    ds = [
        date(2024, 12, 31),
        date(2025, 3, 31),
    ]
    vs = [600.0, 100.0]
    assert infer_hk_main_indicator_fiscal_year_end_month(ds, vs) == 12


def test_infer_prefers_march_fy_when_both_dec_and_mar_signals() -> None:
    """Dec->Mar drop can misfire on March-FY names when FY profit collapses."""
    ds = [
        date(2024, 3, 31),
        date(2024, 6, 30),
        date(2024, 12, 31),
        date(2025, 3, 31),
    ]
    vs = [800.0, 200.0, 900.0, 100.0]
    assert infer_hk_main_indicator_fiscal_year_end_month(ds, vs) == 3


def test_infer_annual_only_march_months() -> None:
    ds = [date(2022, 3, 31), date(2023, 3, 31)]
    vs = [100.0, 110.0]
    assert infer_hk_main_indicator_fiscal_year_end_month(ds, vs) == 3


def test_deaccum_ocf_aligned_matches_income_fiscal_blocks() -> None:
    rows = [
        (date(2024, 3, 31), 900.0, 90.0),
        (date(2024, 6, 30), 100.0, 10.0),
        (date(2024, 9, 30), 250.0, 25.0),
        (date(2024, 12, 31), 400.0, 40.0),
        (date(2025, 3, 31), 550.0, 55.0),
    ]
    _pairs, fy = deaccumulate_hk_main_indicator_income_rows(rows)
    ocf_ytd = [1000.0, 100.0, 250.0, 400.0, 550.0]
    ocf_d = deaccumulate_hk_ytd_scalars_aligned(rows, fy, ocf_ytd, field_name="ocf")
    assert ocf_d[0] == 1000.0
    assert ocf_d[1:] == [100.0, 150.0, 150.0, 150.0]


def test_deaccum_march_fy_four_quarters() -> None:
    # Leading March annual gives Mar->Jun drop for inference; next FY is four cumulants.
    rows = [
        (date(2024, 3, 31), 900.0, 90.0),
        (date(2024, 6, 30), 100.0, 10.0),
        (date(2024, 9, 30), 250.0, 25.0),
        (date(2024, 12, 31), 400.0, 40.0),
        (date(2025, 3, 31), 550.0, 55.0),
    ]
    out, _fy = deaccumulate_hk_main_indicator_income_rows(rows)
    assert out[0] == (900.0, 90.0)
    assert out[1:] == [
        (100.0, 10.0),
        (150.0, 15.0),
        (150.0, 15.0),
        (150.0, 15.0),
    ]


def test_deaccum_december_fy_four_quarters() -> None:
    # Trailing Mar Q1 of next calendar FY gives Dec->Mar drop for inference.
    rows = [
        (date(2024, 3, 31), 100.0, 10.0),
        (date(2024, 6, 30), 250.0, 25.0),
        (date(2024, 9, 30), 400.0, 40.0),
        (date(2024, 12, 31), 550.0, 55.0),
        (date(2025, 3, 31), 120.0, 12.0),
    ]
    out, _fy = deaccumulate_hk_main_indicator_income_rows(rows)
    assert out[:4] == [
        (100.0, 10.0),
        (150.0, 15.0),
        (150.0, 15.0),
        (150.0, 15.0),
    ]
    assert out[4] == (120.0, 12.0)


def test_deaccum_repairs_year_end_below_prior_ytd_same_fy() -> None:
    """When full-year cumulant is below prior 9M (feed restatement), clamp then diff."""
    rows = [
        (date(2020, 3, 31), 500.0, 50.0),
        (date(2020, 6, 30), 10.0, 1.0),
        (date(2020, 9, 30), 20.0, 2.0),
        (date(2020, 12, 31), 40.0, 4.0),
        (date(2021, 3, 31), 35.0, 3.5),
    ]
    out, _fy = deaccumulate_hk_main_indicator_income_rows(rows)
    assert out[0] == (500.0, 50.0)
    assert out[-1][0] == 0.0 and out[-1][1] == 0.0


def test_deaccum_rejects_non_monotonic_cumulative() -> None:
    rows = [
        (date(2024, 3, 31), 900.0, 90.0),
        (date(2024, 6, 30), 100.0, 10.0),
        (date(2024, 9, 30), 80.0, 8.0),
    ]
    with pytest.raises(ValueError, match="cumulative series decreased"):
        deaccumulate_hk_main_indicator_income_rows(rows)
