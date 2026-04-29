"""Atomic quality signals + the default signal catalog.

A ``QualitySignal`` is one named, atomic verdict on a single facet of company
quality (e.g. "long-term ROE", "FCF positive", "capital light"). Each signal
exposes:

- the ``status`` (PASS / WARN / FAIL / NOT_EVALUATED)
- the measured ``value`` and ``threshold`` for transparency
- a short Chinese ``detail`` explaining the call

Signals are produced by *builder functions* (one per signal) operating on a
shared ``QualityContext`` that bundles the four upstream quality VOs.
``DEFAULT_SIGNAL_BUILDERS`` is the canonical catalog consumed by
``QualityEvaluator`` (血液检查): six core signals — long-term ROE, ROA,
FCF positivity, earnings cash conversion, OCF consistency, and leverage.
Individual builder functions remain available for tests or custom catalogs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from backend.domain.quality.cash_flow import CashFlowQuality
from backend.domain.quality.health import FinancialHealth
from backend.domain.quality.profitability import Profitability
from backend.domain.quality.stability import Stability

__all__ = [
    "SignalStatus",
    "QualitySignal",
    "QualityContext",
    "SignalBuilder",
    "CORE_QUALITY_SIGNAL_BUILDERS",
    "DEFAULT_SIGNAL_BUILDERS",
    "long_term_roe",
    "roa_quality",
    "high_gross_margin",
    "fcf_long_term_positive",
    "ocf_consistency",
    "earnings_cash_backed",
    "capital_light",
    "stable_roe",
    "stable_gross_margin",
    "stable_earnings_growth",
    "low_leverage",
    "liquidity_current",
    "liquidity_quick",
]


class SignalStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NOT_EVALUATED = "n/a"


@dataclass(frozen=True)
class QualitySignal:
    """A single named quality verdict with the evidence behind the call."""

    name: str
    label: str
    status: SignalStatus
    value: float | None
    threshold: float | None
    detail: str


@dataclass(frozen=True)
class QualityContext:
    """Bundle of the four upstream quality VOs passed to every signal builder."""

    profitability: Profitability
    cash_flow: CashFlowQuality
    stability: Stability
    health: FinancialHealth


SignalBuilder = Callable[[QualityContext], QualitySignal]


def _na(name: str, label: str, reason: str) -> QualitySignal:
    return QualitySignal(
        name=name,
        label=label,
        status=SignalStatus.NOT_EVALUATED,
        value=None,
        threshold=None,
        detail=reason,
    )


# ---------------------------------------------------------------------- #
# Profitability signals
# ---------------------------------------------------------------------- #


def long_term_roe(ctx: QualityContext) -> QualitySignal:
    """ROE 长期表现：均值 + 达标年比例 双闸门。"""
    name, label = "long_term_roe", "ROE 长期表现"
    roe = ctx.profitability.roe
    avg = roe.average(annual_only=True)
    n = roe.annual_period_count()
    if avg is None or n == 0:
        return _na(name, label, "没有年度 ROE 数据")
    above = roe.years_above(0.15, annual_only=True)
    ratio = above / n
    detail = f"ROE 均值 {avg:.1%}, {above}/{n} 年 ≥ 15%"
    if avg >= 0.15 and ratio >= 0.7:
        status = SignalStatus.PASS
    elif avg >= 0.10:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=avg, threshold=0.15, detail=detail,
    )


def roa_quality(ctx: QualityContext) -> QualitySignal:
    """资产回报质量：剔除杠杆后的真实生意效率。"""
    name, label = "roa_quality", "资产回报质量"
    roa = ctx.profitability.roa
    avg = roa.average(annual_only=True)
    if avg is None:
        return _na(name, label, "没有年度 ROA 数据")
    detail = f"ROA 均值 {avg:.1%}"
    if avg >= 0.08:
        status = SignalStatus.PASS
    elif avg >= 0.04:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=avg, threshold=0.08, detail=detail,
    )


def high_gross_margin(ctx: QualityContext) -> QualitySignal:
    """高毛利能力：定价权 / 差异化的代理指标。"""
    name, label = "high_gross_margin", "高毛利能力"
    gm = ctx.profitability.gross_margin
    avg = gm.average(annual_only=True)
    if avg is None:
        return _na(name, label, "没有毛利率数据")
    detail = f"毛利率均值 {avg:.1%}"
    if avg >= 0.40:
        status = SignalStatus.PASS
    elif avg >= 0.25:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=avg, threshold=0.40, detail=detail,
    )


# ---------------------------------------------------------------------- #
# Cash-flow signals
# ---------------------------------------------------------------------- #


def fcf_long_term_positive(ctx: QualityContext) -> QualitySignal:
    """FCF 长期为正：自由现金流的可持续性。"""
    name, label = "fcf_long_term_positive", "FCF 长期为正"
    cf = ctx.cash_flow
    n = cf.total_periods
    if n == 0:
        return _na(name, label, "没有 FCF 数据")
    pos = cf.positive_periods
    ratio = pos / n
    detail = f"{pos}/{n} 期 自由现金流 > 0"
    if ratio >= 0.7:
        status = SignalStatus.PASS
    elif ratio >= 0.5:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=ratio, threshold=0.7, detail=detail,
    )


def ocf_consistency(ctx: QualityContext) -> QualitySignal:
    """OCF 稳定为正：经营本身的造血能力（与 capex 无关）。"""
    name, label = "ocf_consistency", "OCF 稳定为正"
    cf = ctx.cash_flow
    n = cf.ocf_total_periods
    if n == 0:
        return _na(name, label, "没有 OCF 数据")
    pos = cf.ocf_positive_periods
    ratio = pos / n
    detail = f"{pos}/{n} 期 OCF > 0"
    if ratio >= 0.8:
        status = SignalStatus.PASS
    elif ratio >= 0.6:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=ratio, threshold=0.8, detail=detail,
    )


def earnings_cash_backed(ctx: QualityContext) -> QualitySignal:
    """利润现金兑现：净利润背后是不是真现金。"""
    name, label = "earnings_cash_backed", "利润现金兑现"
    ratio = ctx.cash_flow.aggregate_conversion_ratio()
    if ratio is None:
        return _na(name, label, "没有可用的 OCF / 净利润对齐数据")
    detail = f"sum(OCF) / sum(净利润) = {ratio:.2f}"
    if ratio >= 0.8:
        status = SignalStatus.PASS
    elif ratio >= 0.5:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=ratio, threshold=0.8, detail=detail,
    )


def capital_light(ctx: QualityContext) -> QualitySignal:
    """资本轻量：经营现金有多少最终留下来变成 FCF。"""
    name, label = "capital_light", "资本轻量"
    intensity = ctx.cash_flow.aggregate_capex_intensity()
    if intensity is None:
        return _na(name, label, "没有可用的 Capex / OCF 对齐数据")
    detail = f"sum(Capex) / sum(OCF) = {intensity:.2f}"
    # Lower is better; threshold direction is inverted.
    if intensity <= 0.3:
        status = SignalStatus.PASS
    elif intensity <= 0.6:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=intensity, threshold=0.3, detail=detail,
    )


# ---------------------------------------------------------------------- #
# Stability signals
# ---------------------------------------------------------------------- #


def stable_roe(ctx: QualityContext) -> QualitySignal:
    """ROE 一致性：年度 ROE 标准差。"""
    name, label = "stable_roe", "ROE 一致性"
    sd = ctx.stability.roe_stddev()
    if sd is None:
        return _na(name, label, "年度 ROE 数据点不足")
    detail = f"ROE 年度标准差 {sd*100:.2f}pp"
    # Lower is better; thresholds in absolute percentage points.
    if sd <= 0.05:
        status = SignalStatus.PASS
    elif sd <= 0.10:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=sd, threshold=0.05, detail=detail,
    )


def stable_gross_margin(ctx: QualityContext) -> QualitySignal:
    """毛利率稳定：定价权 / 成本控制的代理指标。"""
    name, label = "stable_gross_margin", "毛利率稳定"
    sd = ctx.stability.gross_margin_stddev()
    if sd is None:
        return _na(name, label, "年度毛利率数据点不足")
    detail = f"毛利率年度标准差 {sd*100:.2f}pp"
    if sd <= 0.03:
        status = SignalStatus.PASS
    elif sd <= 0.06:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=sd, threshold=0.03, detail=detail,
    )


def stable_earnings_growth(ctx: QualityContext) -> QualitySignal:
    """盈余增长平稳：YoY 增长率的变异系数。"""
    name, label = "stable_earnings_growth", "盈余增长平稳"
    cv = ctx.stability.earnings_growth_volatility()
    if cv is None:
        return _na(name, label, "年度增长率数据点不足或均值近零")
    detail = f"年度增长率 CV = {cv:.0%}"
    if cv <= 1.0:
        status = SignalStatus.PASS
    elif cv <= 2.5:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=cv, threshold=1.0, detail=detail,
    )


# ---------------------------------------------------------------------- #
# Financial-health signals (limited until upstream gains liquidity etc.)
# ---------------------------------------------------------------------- #


def low_leverage(ctx: QualityContext) -> QualitySignal:
    """低杠杆：年度资产负债率均值。"""
    name, label = "low_leverage", "低杠杆"
    avg = ctx.health.average_debt_ratio()
    if avg is None:
        return _na(name, label, "没有年度资产负债率数据")
    detail = f"资产负债率均值 {avg:.1%}"
    if avg <= 0.5:
        status = SignalStatus.PASS
    elif avg <= 0.7:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=avg, threshold=0.5, detail=detail,
    )


def liquidity_current(ctx: QualityContext) -> QualitySignal:
    """短期偿付：年度流动比率均值。

    流动比率 (current ratio) = 流动资产 / 流动负债。1.5x 以上属健康，
    低于 1.0x 表示流动负债已超过流动资产，存在显著短期偿付压力。
    """
    name, label = "liquidity_current", "短期偿付"
    avg = ctx.health.average_current_ratio()
    if avg is None:
        return _na(name, label, "没有年度流动比率数据")
    detail = f"流动比率均值 {avg:.2f}x"
    if avg >= 1.5:
        status = SignalStatus.PASS
    elif avg >= 1.0:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=avg, threshold=1.5, detail=detail,
    )


def liquidity_quick(ctx: QualityContext) -> QualitySignal:
    """从严偿付：年度速动比率均值。

    速动比率 (quick ratio) = (流动资产 - 存货) / 流动负债。剔除变现性差的
    存货后的更严苛口径，1.0x 以上是审慎健康。HK 上游不公布该字段，故对
    港股自动 ``NOT_EVALUATED``。
    """
    name, label = "liquidity_quick", "从严偿付"
    avg = ctx.health.average_quick_ratio()
    if avg is None:
        return _na(name, label, "上游未公布速动比率（如港股）或年度数据点不足")
    detail = f"速动比率均值 {avg:.2f}x"
    if avg >= 1.0:
        status = SignalStatus.PASS
    elif avg >= 0.5:
        status = SignalStatus.WARN
    else:
        status = SignalStatus.FAIL
    return QualitySignal(
        name=name, label=label, status=status,
        value=avg, threshold=1.0, detail=detail,
    )


CORE_QUALITY_SIGNAL_BUILDERS: tuple[SignalBuilder, ...] = (
    long_term_roe,
    roa_quality,
    fcf_long_term_positive,
    earnings_cash_backed,
    ocf_consistency,
    low_leverage,
)

DEFAULT_SIGNAL_BUILDERS: tuple[SignalBuilder, ...] = CORE_QUALITY_SIGNAL_BUILDERS
