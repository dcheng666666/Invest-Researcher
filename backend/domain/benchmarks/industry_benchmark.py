"""Static industry benchmark row: medians / reference levels for peer context.

``industry_key`` must match the upstream ``行业`` string (or a normalized alias
your seed data defines) — there is no fuzzy matching in the repository layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndustryBenchmark:
    industry_key: str
    as_of: str
    roe_median: float | None = None
    roa_median: float | None = None
    gross_margin_median: float | None = None
    debt_ratio_median: float | None = None
    source_note: str | None = None
