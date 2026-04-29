"""Step 4: 生意逻辑 — moat / competitive advantage (rule + LLM).

Display-only in the public 5-step framework: the verdict / charts still
stream to the UI, but the score is excluded from the overall rating
(see ``StepConfig.scoring`` in ``step_registry``).
"""

from __future__ import annotations

from backend.application.analysis.context import AnalysisContext
from backend.application.analysis.prompts import load_prompt
from backend.application.analysis.results import MoatResult
from backend.application.analysis.steps._helpers import (
    format_history_for_prompt,
    series_to_period_metrics,
)
from backend.application.ports.llm_client import LLMClient
from backend.domain.financials.series import FinancialSeries
from backend.domain.verdict import Verdict


def _classify_gross_margin_trend(series: FinancialSeries) -> str:
    if len(series) < 3:
        return ""
    values = series.values
    midpoint = len(values) // 2
    first_half = values[:midpoint]
    second_half = values[midpoint:]
    avg_first = sum(first_half) / len(first_half) if first_half else 0
    avg_second = sum(second_half) / len(second_half) if second_half else 0
    if avg_second > avg_first * 1.02:
        return "上升"
    if avg_second < avg_first * 0.98:
        return "下降"
    return "稳定"


def analyze(ctx: AnalysisContext, llm: LLMClient | None = None) -> MoatResult:
    history = ctx.financials
    gross_margin = history.metric_series("gross_margin")
    net_margin = history.metric_series("net_margin")
    selling_expense = history.metric_series("selling_expense_ratio")

    gm_trend = _classify_gross_margin_trend(gross_margin)

    data_table = format_history_for_prompt(
        history,
        ["gross_margin", "net_margin", "selling_expense_ratio", "revenue"],
    )

    user_prompt = (
        f"请分析 {ctx.name}({ctx.code}) 的护城河和竞争优势。\n\n"
        f"财务数据：\n{data_table}\n\n"
        f"毛利率趋势：{gm_trend}"
    )
    llm_text = (
        llm.complete(load_prompt("moat"), user_prompt)
        if llm is not None
        else "未启用 LLM 客户端。"
    )

    verdict = Verdict.NEUTRAL
    score = 3
    if gm_trend == "上升":
        verdict, score = Verdict.EXCELLENT, 5
    elif gm_trend == "稳定" and gross_margin:
        avg_gm = sum(gross_margin.values) / len(gross_margin)
        if avg_gm >= 0.40:
            verdict, score = Verdict.EXCELLENT, 5
        elif avg_gm >= 0.25:
            verdict, score = Verdict.GOOD, 4
    elif gm_trend == "下降":
        verdict, score = Verdict.WARNING, 2

    verdict_reason = f"毛利率趋势{gm_trend}。" if gm_trend else ""

    return MoatResult(
        gross_margins=series_to_period_metrics(gross_margin),
        net_margins=series_to_period_metrics(net_margin),
        rd_expense_ratios=[],
        selling_expense_ratios=series_to_period_metrics(selling_expense),
        gross_margin_trend=gm_trend,
        llm_analysis=llm_text,
        verdict=verdict,
        verdict_reason=verdict_reason,
        score=score,
    )
