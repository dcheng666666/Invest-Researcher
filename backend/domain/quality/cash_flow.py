"""Cash-flow quality value object: behaviors over four aligned cash-flow series.

Holds single-period (de-accumulated) ``FinancialSeries`` for free cash flow,
operating cash flow, capex and net profit, all sourced from the same
``FinancialHistory`` so the series are period-aligned. Exposes four behavior
families, mirroring the design's evaluation dimensions:

1. **earnings-to-cash conversion** — ``aggregate_conversion_ratio`` =
   ``sum(OCF) / sum(NetProfit)`` over the window; reveals whether reported
   profit is backed by real cash.
2. **free cash flow stability** — positive-period count over total (kept as
   ``positive_periods`` / ``total_periods`` for back-compat with the existing
   ``QualityEvaluator``).
3. **operating cash consistency** — same counters but on raw OCF; FCF
   negatives driven by heavy capex are not the same as broken operations.
4. **capex intensity** — ``aggregate_capex_intensity`` =
   ``sum(Capex) / sum(OCF)``; the canonical "capital light vs capital heavy"
   lens (low ratio ⇒ printing-press business).

Aggregation is done on summed numerators/denominators rather than averaging
per-period ratios because cash flow ratios explode in low-denominator
quarters (a textbook earnings-quality pitfall). Per-period ratio series are
still exposed for charting but the assessment-grade scalars use the
aggregate form.

Volatility / coefficient-of-variation lives in a separate ``Stability`` VO
to keep responsibilities crisp.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.financials.history import FinancialHistory
from backend.domain.financials.series import FinancialSeries

__all__ = ["CashFlowQuality"]


def _aligned_ratio_series(
    numerator: FinancialSeries, denominator: FinancialSeries
) -> FinancialSeries:
    """Pair-wise ratio over periods present in both series.

    Drops periods where the denominator is missing or zero (would otherwise
    blow up the ratio).
    """
    den_by_period = {p: v for p, v in denominator.pairs}
    pairs = []
    for p, num in numerator.pairs:
        den = den_by_period.get(p)
        if den is None or den == 0:
            continue
        pairs.append((p, num / den))
    return FinancialSeries(tuple(pairs))


def _aggregate_ratio(
    numerator: FinancialSeries, denominator: FinancialSeries
) -> float | None:
    """``sum(numerator) / sum(denominator)`` restricted to period-matched pairs.

    Both sums are taken over periods where the numerator AND a non-zero
    denominator are both present, so a missing period on one side does not
    silently leak the other side's value into the ratio.

    Robust against per-period small-denominator blow-ups (the canonical
    failure mode of averaging per-period ratios — e.g. a quarter where net
    profit is near zero will dominate ``mean(OCF/NP)`` even though it carries
    almost no economic weight). This is the standard aggregation used in the
    earnings-quality literature (Sloan 1996, Penman) and in Buffett's
    OCF/NP discussions.
    """
    den_by_period = {p: v for p, v in denominator.pairs}
    num_total = 0.0
    den_total = 0.0
    matched = False
    for p, num in numerator.pairs:
        den = den_by_period.get(p)
        if den is None or den == 0:
            continue
        num_total += num
        den_total += den
        matched = True
    if not matched:
        return None
    return num_total / den_total


@dataclass(frozen=True)
class CashFlowQuality:
    """Quarter-aligned cash-flow series + behaviors for cash-quality assessment.

    The four series are all single-period: A-share uses ``YTD_CUMULATIVE`` and
    ``FinancialHistory`` de-accumulates; HK ingest converts Eastmoney fiscal-YTD
    cash flows to discrete quarters (same pipeline as income) so
    ``single_quarter_series`` stays consistent with ``DISCRETE`` flags.
    """

    free_cash_flow: FinancialSeries
    operating_cash_flow: FinancialSeries
    capex: FinancialSeries
    net_profit: FinancialSeries

    @classmethod
    def from_history(cls, history: FinancialHistory) -> "CashFlowQuality":
        return cls(
            free_cash_flow=history.single_quarter_series("free_cash_flow"),
            operating_cash_flow=history.single_quarter_series("operating_cash_flow"),
            capex=history.single_quarter_series("capex"),
            net_profit=history.single_quarter_series("net_profit"),
        )

    # ------------------------------------------------------------------ #
    # FCF stability — backward-compatible with the existing evaluator.
    # ------------------------------------------------------------------ #

    @property
    def positive_periods(self) -> int:
        """Number of periods where FCF > 0."""
        return sum(1 for v in self.free_cash_flow.values if v > 0)

    @property
    def total_periods(self) -> int:
        """Number of periods with an FCF observation."""
        return len(self.free_cash_flow)

    # ------------------------------------------------------------------ #
    # Operating cash consistency — same shape on raw OCF.
    # ------------------------------------------------------------------ #

    @property
    def ocf_positive_periods(self) -> int:
        """Number of periods where OCF > 0. A clean read of the operating
        engine, independent of capex intensity."""
        return sum(1 for v in self.operating_cash_flow.values if v > 0)

    @property
    def ocf_total_periods(self) -> int:
        return len(self.operating_cash_flow)

    # ------------------------------------------------------------------ #
    # Earnings-to-cash conversion — OCF / NetProfit.
    # ------------------------------------------------------------------ #

    @property
    def conversion_ratios(self) -> FinancialSeries:
        """Per-period ``OCF / NetProfit``, for charting / inspection only.

        Quarters with seasonally-small net profit make this series very noisy
        (the cyclic auto industry routinely shows |ratio| > 50). For the
        evaluation-grade scalar use ``aggregate_conversion_ratio`` instead,
        which sums numerator and denominator before dividing.
        """
        return _aligned_ratio_series(self.operating_cash_flow, self.net_profit)

    def aggregate_conversion_ratio(self) -> float | None:
        """``sum(OCF) / sum(NetProfit)`` over the full window. ~1.0 == healthy
        cash-backed earnings; persistently <0.5 signals accruals-driven profit
        (a classic Sloan-style red flag); >>1.0 means OCF is buoyed by
        non-profit sources (working-capital release, depreciation add-back)."""
        return _aggregate_ratio(self.operating_cash_flow, self.net_profit)

    # ------------------------------------------------------------------ #
    # Capex intensity — Capex / OCF.
    # ------------------------------------------------------------------ #

    @property
    def capex_intensity_ratios(self) -> FinancialSeries:
        """Per-period ``Capex / OCF``, for charting / inspection only.

        Same caveat as ``conversion_ratios`` — capex is lumpy by nature, so
        single-period readings spike when a major project lands. For
        assessment use ``aggregate_capex_intensity`` instead.
        """
        return _aligned_ratio_series(self.capex, self.operating_cash_flow)

    def aggregate_capex_intensity(self) -> float | None:
        """``sum(Capex) / sum(OCF)`` over the full window. <0.3 reads as
        capital-light (printing-press businesses); >0.7 means most operating
        cash is reinvested back into PP&E rather than turning into FCF."""
        return _aggregate_ratio(self.capex, self.operating_cash_flow)
