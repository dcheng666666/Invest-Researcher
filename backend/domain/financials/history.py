"""FinancialHistory aggregate root: a security's chronologically ordered reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from backend.domain.financials.accounting import PeriodPresentation
from backend.domain.financials.period import ReportPeriod
from backend.domain.financials.report import FinancialReport
from backend.domain.financials.series import FinancialSeries
from backend.domain.stocks.symbol import Symbol

__all__ = ["FinancialHistory"]


_QuarterKey = tuple[int, int]


def _resolve_attr(report: FinancialReport, attr: str) -> float | None:
    """Look up ``attr`` on the report's IS, CFS, or metrics component.

    The component namespaces are disjoint by design, so first match wins.
    """
    for owner in (
        report.income_statement,
        report.cash_flow_statement,
        report.metrics,
    ):
        if hasattr(owner, attr):
            return getattr(owner, attr)
    raise AttributeError(f"No financial attribute {attr!r} on report")


@dataclass(frozen=True)
class FinancialHistory:
    """Per-security ordered collection of ``FinancialReport`` filings.

    Invariants enforced at construction:
    1. Every report belongs to ``security_id``.
    2. Reports are sorted strictly ascending by period (no duplicates).
    3. All reports share the same ``period_presentation`` so cross-period
       de-accumulation has a single, well-defined meaning.
    """

    security_id: Symbol
    reports: tuple[FinancialReport, ...]

    def __post_init__(self) -> None:
        for r in self.reports:
            if r.security_id != self.security_id:
                raise ValueError(
                    f"Report {r.identity} does not belong to {self.security_id}"
                )
        for prev, curr in zip(self.reports, self.reports[1:]):
            if not (prev.period < curr.period):
                raise ValueError(
                    f"Reports must be strictly ascending: {prev.period} -> {curr.period}"
                )
        if self.reports:
            presentation = self.reports[0].accounting.period_presentation
            for r in self.reports:
                if r.accounting.period_presentation is not presentation:
                    raise ValueError(
                        "FinancialHistory requires a uniform period_presentation"
                    )

    @classmethod
    def of(
        cls, security_id: Symbol, reports: Iterable[FinancialReport]
    ) -> "FinancialHistory":
        ordered = tuple(sorted(reports, key=lambda r: r.period))
        return cls(security_id=security_id, reports=ordered)

    def has_data(self) -> bool:
        return bool(self.reports)

    def series_for(self, attr: str) -> FinancialSeries:
        """Cross-period series for any IS / CFS / metrics attribute."""
        return FinancialSeries.of(
            (r.period, _resolve_attr(r, attr)) for r in self.reports
        )

    def income_series(self, attr: str) -> FinancialSeries:
        return FinancialSeries.of(
            (r.period, getattr(r.income_statement, attr)) for r in self.reports
        )

    def metric_series(self, attr: str) -> FinancialSeries:
        return FinancialSeries.of(
            (r.period, getattr(r.metrics, attr)) for r in self.reports
        )

    def single_quarter_series(self, attr: str) -> FinancialSeries:
        ordered, single, lookup = self._single_quarter_map(attr)
        return FinancialSeries(
            tuple(
                (lookup[(y, q)], round(single[(y, q)], 2))
                for y, q in ordered
                if (y, q) in single
            )
        )

    def ttm_series(self, attr: str) -> FinancialSeries:
        _, _, lookup = self._single_quarter_map(attr)
        return FinancialSeries(
            tuple((lookup[key], value) for key, value in self._ttm_quarter_pairs(attr))
        )

    # ------------------------------------------------------------------ #
    # Internal helpers (keep private methods grouped below public API)
    # ------------------------------------------------------------------ #

    @property
    def _presentation(self) -> PeriodPresentation:
        return self.reports[0].accounting.period_presentation

    def _ordered_cum_map(
        self, getter: Callable[[FinancialReport], float | None]
    ) -> tuple[list[_QuarterKey], dict[_QuarterKey, float], dict[_QuarterKey, ReportPeriod]]:
        cum: dict[_QuarterKey, float] = {}
        period_lookup: dict[_QuarterKey, ReportPeriod] = {}
        for r in self.reports:
            v = getter(r)
            if v is None:
                continue
            key = (r.period.fiscal_year, r.period.quarter)
            cum[key] = float(v)
            period_lookup[key] = r.period
        ordered = sorted(cum.keys())
        return ordered, cum, period_lookup

    def _single_quarter_map(
        self, attr: str
    ) -> tuple[list[_QuarterKey], dict[_QuarterKey, float], dict[_QuarterKey, ReportPeriod]]:
        getter: Callable[[FinancialReport], float | None] = lambda r: _resolve_attr(r, attr)
        ordered, cum, lookup = self._ordered_cum_map(getter)
        single: dict[_QuarterKey, float] = {}
        if not ordered:
            return ordered, single, lookup
        is_discrete = self._presentation is PeriodPresentation.DISCRETE
        for y, q in ordered:
            c = cum[(y, q)]
            if is_discrete or q == 1:
                single[(y, q)] = c
            else:
                prev = cum.get((y, q - 1))
                if prev is not None:
                    single[(y, q)] = c - prev
        return ordered, single, lookup

    def _ttm_quarter_pairs(self, attr: str) -> list[tuple[_QuarterKey, float]]:
        ordered, single, _ = self._single_quarter_map(attr)

        def _prev(y: int, q: int) -> _QuarterKey:
            return (y - 1, 4) if q == 1 else (y, q - 1)

        out: list[tuple[_QuarterKey, float]] = []
        for y, q in ordered:
            vals: list[float] = []
            cy, cq = y, q
            for _ in range(4):
                v = single.get((cy, cq))
                if v is None:
                    break
                vals.append(v)
                cy, cq = _prev(cy, cq)
            if len(vals) == 4:
                out.append(((y, q), round(sum(vals), 2)))
        return out
