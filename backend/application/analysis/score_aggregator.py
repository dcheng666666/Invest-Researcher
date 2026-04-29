"""Aggregate per-step scores into an overall 0..5 rating."""

from __future__ import annotations

from backend.application.analysis.step_registry import STEP_CONFIGS


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
