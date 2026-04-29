"""Domain service: rate the valuation snapshot vs its history."""

from __future__ import annotations

import logging

from backend.domain.valuation.assessment import ValuationAssessment
from backend.domain.valuation.history import ValuationHistory
from backend.domain.valuation.multiples import PEGRatio
from backend.domain.valuation.snapshot import ValuationSnapshot
from backend.domain.verdict import Verdict

__all__ = ["ValuationEvaluator"]

logger = logging.getLogger(__name__)


class ValuationEvaluator:
    """Score valuation attractiveness with a z-score / percentile cascade.

    ``peg`` is taken as an explicit dependency rather than a snapshot field
    because PEG requires a growth signal that lives outside the snapshot
    (see modeling: ``PEGRatio`` is a sibling ``ValuationMultiple``).
    """

    def evaluate(
        self,
        snapshot: ValuationSnapshot,
        history: ValuationHistory,
        *,
        peg: PEGRatio | None = None,
    ) -> ValuationAssessment:
        current_pe = snapshot.pe_value
        peg_value = peg.value if peg is not None else None
        band = history.band()
        percentile = history.percentile_of(current_pe)

        pe_mean = band.mean if band is not None else None
        pe_std = band.std_dev if band is not None else None
        pe_pct = percentile.value if percentile is not None else None

        if (
            current_pe is not None
            and pe_mean is not None
            and pe_std is not None
            and pe_std > 0
        ):
            z = (current_pe - pe_mean) / pe_std
            z_desc = (
                f"当前PE {current_pe:.1f}倍，历史均值{pe_mean:.1f}倍（标准差{pe_std:.1f}），"
                f"偏离{z:+.2f}σ"
            )
            if z <= -1.0:
                if peg_value is not None and peg_value < 1:
                    return ValuationAssessment(
                        verdict=Verdict.EXCELLENT,
                        reason=(
                            f"{z_desc}，"
                            f"PEG仅{peg_value:.2f}，业绩仍在增长但估值显著低于历史中枢，"
                            f"属于黄金坑/戴维斯双击潜伏期。"
                        ),
                        score=5,
                        z_score=z,
                        percentile=pe_pct,
                    )
                return ValuationAssessment(
                    verdict=Verdict.GOOD,
                    reason=f"{z_desc}，估值处于历史偏低区间。",
                    score=4,
                    z_score=z,
                    percentile=pe_pct,
                )
            if z >= 2.0:
                return ValuationAssessment(
                    verdict=Verdict.DANGER,
                    reason=(
                        f"{z_desc}，"
                        f"估值严重偏离历史中枢，泡沫风险极高，存在戴维斯双杀的可能。"
                    ),
                    score=1,
                    z_score=z,
                    percentile=pe_pct,
                )
            if z >= 1.0:
                return ValuationAssessment(
                    verdict=Verdict.WARNING,
                    reason=f"{z_desc}，估值显著高于历史中枢，安全边际不足。",
                    score=2,
                    z_score=z,
                    percentile=pe_pct,
                )
            return ValuationAssessment(
                verdict=Verdict.NEUTRAL,
                reason=f"{z_desc}，估值处于合理区间。",
                score=3,
                z_score=z,
                percentile=pe_pct,
            )
        if current_pe is not None and pe_pct is not None:
            if pe_pct <= 0.30:
                return ValuationAssessment(
                    verdict=Verdict.GOOD,
                    reason=f"当前PE {current_pe:.1f}倍，处于近10年{pe_pct:.0%}分位，估值偏低。",
                    score=4,
                    percentile=pe_pct,
                )
            if pe_pct >= 0.80:
                return ValuationAssessment(
                    verdict=Verdict.DANGER,
                    reason=f"当前PE {current_pe:.1f}倍，处于近10年{pe_pct:.0%}分位，估值偏高。",
                    score=1,
                    percentile=pe_pct,
                )
            return ValuationAssessment(
                verdict=Verdict.NEUTRAL,
                reason=f"当前PE {current_pe:.1f}倍，处于近10年{pe_pct:.0%}分位，估值适中。",
                score=3,
                percentile=pe_pct,
            )
        if current_pe is not None:
            if current_pe < 15:
                return ValuationAssessment(
                    verdict=Verdict.GOOD,
                    reason=f"当前PE {current_pe:.1f}倍，估值偏低。",
                    score=4,
                )
            if current_pe > 50:
                return ValuationAssessment(
                    verdict=Verdict.WARNING,
                    reason=f"当前PE {current_pe:.1f}倍，估值偏高。",
                    score=2,
                )
            return ValuationAssessment(
                verdict=Verdict.NEUTRAL,
                reason=f"当前PE {current_pe:.1f}倍，估值适中。",
                score=3,
            )
        logger.warning(
            "ValuationEvaluator.evaluate: no usable valuation data "
            "(as_of=%s, market_cap=%s, history_size=%d)",
            snapshot.as_of_date.isoformat(),
            snapshot.market_cap,
            len(history.snapshots),
        )
        return ValuationAssessment(
            verdict=Verdict.NEUTRAL,
            reason="无法获取估值数据。",
            score=3,
        )
