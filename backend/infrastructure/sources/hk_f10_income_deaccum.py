"""Eastmoney HK F10 main-indicator income: cumulative YTD -> discrete quarters.

The main-indicator feed publishes ``OPERATE_INCOME`` and ``HOLDER_PROFIT`` as
fiscal year-to-date cumulants for interim rows (with a full-year row at the
fiscal year-end). ``FinancialHistory`` assumes ``DISCRETE`` quarterly flows
for TTM; this module converts raw cumulants to true single-period amounts
before ``FinancialReport`` construction.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

logger = logging.getLogger(__name__)

__all__ = [
    "deaccumulate_hk_main_indicator_income_rows",
    "deaccumulate_hk_ytd_scalars_aligned",
    "infer_hk_main_indicator_fiscal_year_end_month",
]


def _fy_end_year_march_fye(period_end: date) -> int:
    """Fiscal year label = calendar year of the March fiscal year-end."""
    return period_end.year if period_end.month <= 3 else period_end.year + 1


def _fy_end_year_december_fye(period_end: date) -> int:
    """Fiscal year label = calendar year of the December fiscal year-end."""
    return period_end.year


def infer_hk_main_indicator_fiscal_year_end_month(
    sorted_dates: Sequence[date],
    anchor_values: Sequence[float | None],
) -> int:
    """Infer fiscal year-end month (3 or 12) from cumulative profit-like series.

    Uses sharp drops after a year-end row vs the first interim of the new year
    (March FY: Mar >> Jun; December FY: Dec >> Mar). Adjacent rows are evaluated
    in **chronological** order; pairs with missing anchors are skipped.

    When both patterns appear, **March FY wins** if any Mar→Jun drop exists:
    Dec→Mar can misfire for March-FY issuers when full-year profit falls below the
    prior December YTD cumulant.

    Raises:
        ValueError: empty input, unexpected report months, ambiguous pattern,
            or no usable anchor values.
    """
    if not sorted_dates or len(sorted_dates) != len(anchor_values):
        raise ValueError("sorted_dates and anchor_values must be same-length non-empty")

    if not any(v is not None for v in anchor_values):
        raise ValueError("no non-None anchor values to infer fiscal year-end month")

    months = {d.month for d in sorted_dates}
    if not months <= {3, 6, 9, 12}:
        raise ValueError(
            f"HK F10 main-indicator report months must be subset of {{3,6,9,12}}, got {months!r}"
        )

    mar_drop_score = 0
    dec_drop_score = 0
    ratio_floor = 1.25
    for i in range(len(sorted_dates) - 1):
        d1, d2 = sorted_dates[i], sorted_dates[i + 1]
        v1, v2 = anchor_values[i], anchor_values[i + 1]
        if v1 is None or v2 is None or v1 <= 0 or v2 <= 0:
            continue
        if d1.month == 3 and d2.month == 6 and v1 > v2 * ratio_floor:
            mar_drop_score += 1
        if d1.month == 12 and d2.month == 3 and v1 > v2 * ratio_floor:
            dec_drop_score += 1

    # March->June (full year vs new FY Q1) is a reliable March-FY signal. Dec->Mar
    # can false-trigger when March-FY earnings fall: 9M Dec cumulant may exceed the
    # following March full-year figure — prefer March FY whenever Mar->Jun appears.
    if mar_drop_score > 0:
        return 3
    if dec_drop_score > 0:
        return 12
    # Annual-only history (repeated March rows) — treat as March FY (common HK / PRC ADR).
    if months <= {3}:
        return 3
    raise ValueError(
        "cannot infer HK F10 fiscal year-end month: no year-boundary drop in anchor series "
        f"(months={months!r}); add explicit rules or a different feed for this security"
    )


def _fy_end_year(period_end: date, fiscal_year_end_month: int) -> int:
    if fiscal_year_end_month == 3:
        return _fy_end_year_march_fye(period_end)
    if fiscal_year_end_month == 12:
        return _fy_end_year_december_fye(period_end)
    raise ValueError(f"unsupported fiscal_year_end_month: {fiscal_year_end_month}")


def _enforce_fiscal_ytd_cumulative_monotonic(nums: list[float]) -> list[float]:
    """Eastmoney HK F10 occasionally publishes a full-year figure below a prior YTD
    cumulant (restatement timing). Enforce ``cum[i] <= cum[i+1]`` backward from the
    fiscal year-end row so single-quarter diffs stay well-defined.
    """
    if len(nums) < 2:
        return nums
    adj = list(nums)
    changed = False
    for i in range(len(adj) - 2, -1, -1):
        if adj[i] > adj[i + 1] + 1e-6:
            adj[i] = adj[i + 1]
            changed = True
    if changed:
        logger.warning(
            "HK F10 cumulative adjusted for monotonicity within fiscal year "
            "(upstream YTD vs annual mismatch); raw=%s adjusted=%s",
            nums,
            adj,
        )
    return adj


def _deaccum_strict_cumulative(
    values: list[float | None],
    *,
    fiscal_year_end_month: int,
    report_months_in_fy_order: list[int],
) -> list[float | None]:
    """First row is the first cumulant in the fiscal block; rest are deltas.

    Monotonicity repair runs only when the fiscal block **ends on the fiscal
    year-end month** (e.g. March for March-FY names). Interim-only blocks must
    stay strictly increasing; otherwise upstream data is unusable.
    """
    if not values:
        return []
    if any(v is None for v in values):
        raise ValueError("cumulative series within a fiscal year must not contain None")
    raw_nums: list[float] = [float(v) for v in values]
    if (
        report_months_in_fy_order
        and report_months_in_fy_order[-1] == fiscal_year_end_month
    ):
        nums = _enforce_fiscal_ytd_cumulative_monotonic(raw_nums)
    else:
        nums = raw_nums
    for i in range(1, len(nums)):
        if nums[i] + 1e-6 < nums[i - 1]:
            raise ValueError(
                f"cumulative series decreased within fiscal year after monotonic repair: "
                f"{nums[i - 1]} -> {nums[i]}"
            )
    out: list[float | None] = [nums[0]]
    for i in range(1, len(nums)):
        out.append(nums[i] - nums[i - 1])
    return out


def _expected_first_interim_month(fiscal_year_end_month: int) -> int:
    if fiscal_year_end_month == 3:
        return 6
    if fiscal_year_end_month == 12:
        return 3
    raise ValueError(f"unsupported fiscal_year_end_month: {fiscal_year_end_month}")


def _validate_fy_group_first_month(
    fiscal_year_end_month: int,
    sorted_months: list[int],
) -> None:
    if not sorted_months:
        return
    if len(sorted_months) == 1 and sorted_months[0] == fiscal_year_end_month:
        return
    expected = _expected_first_interim_month(fiscal_year_end_month)
    if sorted_months[0] != expected:
        raise ValueError(
            "HK F10 income deaccumulation requires the first row in each fiscal year "
            f"to be month {expected} (or a lone fiscal year-end month {fiscal_year_end_month}); "
            f"got months {sorted_months} for fiscal_year_end_month={fiscal_year_end_month}"
        )


def _rows_by_fiscal_year(
    rows: list[tuple[date, float | None, float | None]], fy_end_month: int
) -> dict[int, list[int]]:
    by_fy: dict[int, list[int]] = defaultdict(list)
    for i, (d, _, _) in enumerate(rows):
        by_fy[_fy_end_year(d, fy_end_month)].append(i)
    return by_fy


def deaccumulate_hk_ytd_scalars_aligned(
    rows: list[tuple[date, float | None, float | None]],
    fiscal_year_end_month: int,
    ytd_values: list[float | None],
    *,
    field_name: str = "value",
) -> list[float | None]:
    """Convert one fiscal-YTD column (e.g. OCF) to discrete quarters using ``rows`` order.

    ``rows`` must match the same chronological list used for income deaccumulation.
    When any value in a fiscal-year block is missing while others are present, that
    block is left as **raw upstream numbers** (still YTD cumulants) and a warning is
    logged — downstream ``DISCRETE`` semantics do not hold for those rows.
    """
    if len(rows) != len(ytd_values):
        raise ValueError("ytd_values length must match rows")
    if not rows:
        return []

    out: list[float | None] = [None] * len(rows)
    by_fy = _rows_by_fiscal_year(rows, fiscal_year_end_month)

    for fy in sorted(by_fy.keys()):
        idxs = sorted(by_fy[fy], key=lambda i: rows[i][0])
        sorted_months = [rows[i][0].month for i in idxs]
        _validate_fy_group_first_month(fiscal_year_end_month, sorted_months)

        col = [ytd_values[i] for i in idxs]
        if not any(v is not None for v in col):
            continue
        if any(v is None for v in col):
            logger.warning(
                "HK F10 %s: missing values in fiscal year block fy=%s months=%s; "
                "leaving raw YTD cumulants for those rows (DISCRETE semantics not applied)",
                field_name,
                fy,
                sorted_months,
            )
            for j, global_i in enumerate(idxs):
                out[global_i] = col[j]
            continue

        disc = _deaccum_strict_cumulative(
            col,
            fiscal_year_end_month=fiscal_year_end_month,
            report_months_in_fy_order=sorted_months,
        )
        for j, global_i in enumerate(idxs):
            out[global_i] = disc[j]

    return out


def deaccumulate_hk_main_indicator_income_rows(
    rows: list[tuple[date, float | None, float | None]],
) -> tuple[list[tuple[float | None, float | None]], int]:
    """Return ``(discrete (revenue, profit) per row, fiscal_year_end_month)``.

    ``rows`` must be sorted by date ascending.
    """
    if not rows:
        return [], 3

    anchor: list[float | None] = []
    for _, rev, pr in rows:
        if pr is not None:
            anchor.append(pr)
        elif rev is not None:
            anchor.append(rev)
        else:
            anchor.append(None)

    fy_end_month = infer_hk_main_indicator_fiscal_year_end_month(
        [d for d, _, _ in rows],
        anchor,
    )

    by_fy = _rows_by_fiscal_year(rows, fy_end_month)

    out_rev: list[float | None] = [None] * len(rows)
    out_pr: list[float | None] = [None] * len(rows)

    for fy in sorted(by_fy.keys()):
        idxs = sorted(by_fy[fy], key=lambda i: rows[i][0])
        sorted_months = [rows[i][0].month for i in idxs]
        _validate_fy_group_first_month(fy_end_month, sorted_months)

        rev_cum = [rows[i][1] for i in idxs]
        pr_cum = [rows[i][2] for i in idxs]

        if any(r is not None for r in rev_cum):
            if any(r is None for r in rev_cum):
                raise ValueError(
                    "revenue must be all-None or all-non-None within each fiscal year for HK F10 deaccum"
                )
            rev_d = _deaccum_strict_cumulative(
                rev_cum,
                fiscal_year_end_month=fy_end_month,
                report_months_in_fy_order=sorted_months,
            )
        else:
            rev_d = [None] * len(idxs)

        if any(p is not None for p in pr_cum):
            if any(p is None for p in pr_cum):
                raise ValueError(
                    "profit must be all-None or all-non-None within each fiscal year for HK F10 deaccum"
                )
            pr_d = _deaccum_strict_cumulative(
                pr_cum,
                fiscal_year_end_month=fy_end_month,
                report_months_in_fy_order=sorted_months,
            )
        else:
            pr_d = [None] * len(idxs)

        for j, global_i in enumerate(idxs):
            out_rev[global_i] = rev_d[j]
            out_pr[global_i] = pr_d[j]

    return list(zip(out_rev, out_pr, strict=True)), fy_end_month
