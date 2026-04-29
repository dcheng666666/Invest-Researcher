"""Step 3: 厚道程度 — dividend payout ratio + dividend yield."""

from __future__ import annotations

from backend.application.analysis.context import AnalysisContext
from backend.application.analysis.results import PayoutRatioBarPoint, PayoutResult
from backend.domain.dividends.aggregation import aggregate_history
from backend.domain.dividends.amounts import DividendYield, PayoutRatio
from backend.domain.dividends.ratios import compute_dividend_ratios
from backend.domain.financials.history import FinancialHistory
from backend.domain.verdict import Verdict


def _evaluate_dividend_verdict(
    avg_payout: PayoutRatio | None,
    latest_dy: DividendYield | None,
    explicitly_no_dividend: bool,
) -> tuple[Verdict, str, int]:
    if avg_payout is not None:
        ap = avg_payout.value
        dy = latest_dy.value if latest_dy is not None else None
        if ap >= 0.30 and dy is not None and dy >= 0.03:
            return (
                Verdict.EXCELLENT,
                (
                    f"平均分红支付率{ap:.0%}，最新股息率{dy:.1%}，"
                    "不仅证明利润是真实的真金白银，也构筑了股价的安全垫。"
                ),
                5,
            )
        if ap >= 0.20:
            return (
                Verdict.GOOD,
                f"平均分红支付率{ap:.0%}，分红意愿尚可。",
                4,
            )
        if ap < 0.05:
            return (
                Verdict.DANGER,
                (
                    f"平均分红支付率仅{ap:.0%}，几乎不分红，"
                    "需警惕利润造假或重资产黑洞。"
                ),
                1,
            )
        return (
            Verdict.NEUTRAL,
            f"平均分红支付率{ap:.0%}，表现一般。",
            3,
        )
    if explicitly_no_dividend:
        return (
            Verdict.DANGER,
            (
                "公司近年均选择不分配利润，从未进行过现金分红。"
                "需关注利润再投入的回报率，警惕重资产扩张陷阱。"
            ),
            1,
        )
    return (Verdict.NEUTRAL, "无法获取分红数据。", 2)


def analyze(ctx: AnalysisContext) -> PayoutResult:
    snapshot = ctx.snapshot
    history = ctx.financials
    dividends = ctx.dividends

    dividend_record = aggregate_history(dividends)
    explicitly_no_dividend = dividend_record.is_empty and dividends.has_no_distribution

    annual_eps_deducted = _annual_eps_deducted(history)

    ratios = compute_dividend_ratios(
        dividend_record,
        annual_eps_deducted,
        current_price=snapshot.current_price,
    )

    counts_by_year = dict(dividend_record.annual_distribution_counts)
    payout_rows = [
        PayoutRatioBarPoint(
            period=year,
            value=round(ratio.value, 6),
            distribution_count=counts_by_year[year],
        )
        for year, ratio in ratios.payout_pairs
    ]

    verdict, verdict_reason, score = _evaluate_dividend_verdict(
        ratios.avg_payout, ratios.latest_yield, explicitly_no_dividend
    )

    return PayoutResult(
        payout_ratios=payout_rows,
        avg_payout_ratio=(
            round(ratios.avg_payout.value, 4) if ratios.avg_payout is not None else None
        ),
        latest_dividend_yield=(
            round(ratios.latest_yield.value, 4) if ratios.latest_yield is not None else None
        ),
        verdict=verdict,
        verdict_reason=verdict_reason,
        score=score,
    )


def _annual_eps_deducted(history: FinancialHistory) -> dict[str, float]:
    """Per-fiscal-year deducted EPS, derived from reported basic EPS.

    The income statement carries ``eps`` (basic EPS attributable to
    shareholders) plus ``net_profit`` and ``net_profit_deducted``. We rescale
    the reported EPS by the deducted/headline profit ratio so it matches the
    deducted-profit basis used elsewhere in this analysis. The implied
    weighted-average share count is identical on both sides, so the rescaling
    is exact rather than approximate.

    For HK reports ``net_profit_deducted == net_profit`` (both come from
    ``HOLDER_PROFIT``), so the result simply equals ``eps``.
    """
    out: dict[str, float] = {}
    for report in history.reports:
        if not report.period.is_annual:
            continue
        income = report.income_statement
        eps = income.eps
        net_profit = income.net_profit
        deducted = income.net_profit_deducted
        if eps is None or eps <= 0:
            continue
        if net_profit is None or net_profit <= 0 or deducted is None:
            continue
        out[str(report.period.fiscal_year)] = float(eps) * (
            float(deducted) / float(net_profit)
        )
    return out
