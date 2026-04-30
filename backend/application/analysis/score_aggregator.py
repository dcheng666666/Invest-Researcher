"""Aggregate per-step scores into an overall 0..5 rating."""

from __future__ import annotations

from backend.application.analysis.step_registry import STEP_CONFIGS
from backend.domain.verdict import Verdict


def overall_score(scores: list[int]) -> float:
    """Mean of contributing step scores rounded to one decimal.

    ``scores`` is expected to be parallel to ``STEP_CONFIGS`` in registry
    order (one entry per registered step). Steps marked ``scoring=False``
    in ``StepConfig`` are excluded from the mean so display-only steps
    (e.g. 生意逻辑 / moat while the LLM-driven verdict is being matured)
    don't dilute the overall rating. Returns ``0.0`` when no scores
    contribute.
    """
    if not scores:
        return 0.0
    contributing = [s for s, cfg in zip(scores, STEP_CONFIGS) if cfg.scoring]
    if not contributing:
        return 0.0
    return round(sum(contributing) / len(contributing), 1)


def overall_verdict_from_mean(overall: float | None) -> str | None:
    """Map mean overall score (0..5) to the same verdict enum used by steps."""
    if overall is None:
        return None
    x = float(overall)
    if x >= 4.5:
        return Verdict.EXCELLENT.value
    if x >= 3.5:
        return Verdict.GOOD.value
    if x >= 2.5:
        return Verdict.NEUTRAL.value
    if x >= 1.5:
        return Verdict.WARNING.value
    return Verdict.DANGER.value


def overall_verdict_sql_predicate(verdict_normalized: str) -> str | None:
    """SQLite boolean on ``overall_score`` matching ``overall_verdict_from_mean`` bands."""
    v = verdict_normalized.strip().lower()
    bands: dict[str, str] = {
        Verdict.EXCELLENT.value: "(overall_score IS NOT NULL AND overall_score >= 4.5)",
        Verdict.GOOD.value: (
            "(overall_score IS NOT NULL AND overall_score >= 3.5 AND overall_score < 4.5)"
        ),
        Verdict.NEUTRAL.value: (
            "(overall_score IS NOT NULL AND overall_score >= 2.5 AND overall_score < 3.5)"
        ),
        Verdict.WARNING.value: (
            "(overall_score IS NOT NULL AND overall_score >= 1.5 AND overall_score < 2.5)"
        ),
        Verdict.DANGER.value: "(overall_score IS NOT NULL AND overall_score < 1.5)",
    }
    return bands.get(v)
