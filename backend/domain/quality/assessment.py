"""``QualityAssessment``: aggregate verdict over a tuple of ``QualitySignal``s.

Maps signal pass/warn/fail counts to the legacy 5-level ``Verdict`` so that
existing step DTOs (``FinancialHealthResult.verdict / verdict_reason / score`` for
血液检查) keep working without contract changes — while the structured
``signals`` tuple becomes available for future structured display.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.quality.signals import QualitySignal, SignalStatus
from backend.domain.verdict import Verdict

__all__ = ["QualityAssessment"]


_VERDICT_TO_SCORE: dict[Verdict, int] = {
    Verdict.EXCELLENT: 5,
    Verdict.GOOD: 4,
    Verdict.NEUTRAL: 3,
    Verdict.WARNING: 2,
    Verdict.DANGER: 1,
}


@dataclass(frozen=True)
class QualityAssessment:
    """A bundle of named quality signals plus the aggregate verdict.

    The verdict / score / reason are derived from the signal tuple via fixed
    threshold rules, so two assessments built from the same signals always
    agree on their summary.
    """

    signals: tuple[QualitySignal, ...]

    # ------------------------------------------------------------------ #
    # Counters (NOT_EVALUATED is excluded from the denominator everywhere
    # because we only score on signals we actually measured).
    # ------------------------------------------------------------------ #

    @property
    def pass_count(self) -> int:
        return sum(1 for s in self.signals if s.status is SignalStatus.PASS)

    @property
    def warn_count(self) -> int:
        return sum(1 for s in self.signals if s.status is SignalStatus.WARN)

    @property
    def fail_count(self) -> int:
        return sum(1 for s in self.signals if s.status is SignalStatus.FAIL)

    @property
    def not_evaluated_count(self) -> int:
        return sum(
            1 for s in self.signals if s.status is SignalStatus.NOT_EVALUATED
        )

    @property
    def evaluated_count(self) -> int:
        return self.pass_count + self.warn_count + self.fail_count

    # ------------------------------------------------------------------ #
    # Aggregate verdict / score / reason.
    # ------------------------------------------------------------------ #

    @property
    def verdict(self) -> Verdict:
        n = self.evaluated_count
        if n == 0:
            return Verdict.NEUTRAL
        pass_ratio = self.pass_count / n
        fail_ratio = self.fail_count / n

        if pass_ratio >= 0.8 and self.fail_count == 0:
            return Verdict.EXCELLENT
        if pass_ratio >= 0.6 and fail_ratio <= 0.1:
            return Verdict.GOOD
        if fail_ratio >= 0.4 or pass_ratio < 0.2:
            return Verdict.DANGER
        if fail_ratio >= 0.2:
            return Verdict.WARNING
        return Verdict.NEUTRAL

    @property
    def score(self) -> int:
        return _VERDICT_TO_SCORE[self.verdict]

    @property
    def verdict_reason(self) -> str:
        n = self.evaluated_count
        if n == 0:
            return "数据不足，无法评估"
        # List up to 3 representative passing signals and all failing ones —
        # tells the user concretely *why* the verdict landed where it did.
        parts: list[str] = [
            f"达标 {self.pass_count}/{n}",
            f"警示 {self.warn_count}/{n}",
            f"未达 {self.fail_count}/{n}",
        ]
        head = "，".join(parts)

        fails = [s.label for s in self.signals if s.status is SignalStatus.FAIL]
        if fails:
            return f"{head}；未达项：{'、'.join(fails)}"
        warns = [s.label for s in self.signals if s.status is SignalStatus.WARN]
        if warns:
            return f"{head}；警示项：{'、'.join(warns)}"
        return head
