"""Value object capturing a valuation evaluation outcome."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.verdict import Verdict

__all__ = ["ValuationAssessment"]


@dataclass(frozen=True)
class ValuationAssessment:
    """Outcome of running ``ValuationEvaluator`` against a snapshot+history.

    Carries:
    - ``verdict``: qualitative judgement label
    - ``reason``: human-readable rationale (already localised)
    - ``score``: 1..5 integer score for downstream aggregation
    - ``z_score`` / ``percentile``: the signals that triggered the verdict,
      preserved so callers can render or audit the decision.
    """

    verdict: Verdict
    reason: str
    score: int
    z_score: float | None = None
    percentile: float | None = None
