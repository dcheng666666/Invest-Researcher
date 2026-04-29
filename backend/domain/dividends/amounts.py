"""Per-share amount and ratio value objects for dividend metrics."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DividendPerShare", "PayoutRatio", "DividendYield"]


_PAYOUT_RATIO_CAP = 2.0


@dataclass(frozen=True)
class DividendPerShare:
    """Cash dividend declared on a per-share basis, with currency."""

    amount: float
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError(
                f"DividendPerShare must be non-negative, got {self.amount}"
            )
        if not self.currency:
            raise ValueError("DividendPerShare requires a non-empty currency")

    @classmethod
    def zero(cls, currency: str) -> "DividendPerShare":
        return cls(0.0, currency)

    @property
    def is_zero(self) -> bool:
        return self.amount == 0.0

    def __add__(self, other: "DividendPerShare") -> "DividendPerShare":
        if self.currency != other.currency:
            raise ValueError(
                "Cannot add DividendPerShare across currencies: "
                f"{self.currency} vs {other.currency}"
            )
        return DividendPerShare(self.amount + other.amount, self.currency)


@dataclass(frozen=True)
class PayoutRatio:
    """Annual cash dividend / annual net profit (capped at 2.0 for sanity)."""

    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"PayoutRatio must be non-negative, got {self.value}")

    @classmethod
    def of(cls, dividend_total: float, net_profit: float) -> "PayoutRatio | None":
        """Build a PayoutRatio, returning None when the denominator is unusable."""
        if net_profit <= 0:
            return None
        ratio = dividend_total / net_profit
        return cls(min(round(ratio, 4), _PAYOUT_RATIO_CAP))

    @classmethod
    def from_dps_eps(
        cls, dps_amount: float, eps: float | None
    ) -> "PayoutRatio | None":
        """Build a PayoutRatio from per-share figures: DPS / EPS.

        Mathematically equivalent to ``dividend_total / net_profit`` because
        the same weighted-average share count cancels on both sides, so we
        sidestep needing a per-period share count and the systematic bias
        that comes from substituting today's share count for past periods.
        """
        if eps is None or eps <= 0:
            return None
        ratio = dps_amount / eps
        return cls(min(round(ratio, 4), _PAYOUT_RATIO_CAP))


@dataclass(frozen=True)
class DividendYield:
    """Annual dividend per share / current price."""

    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"DividendYield must be non-negative, got {self.value}")

    @classmethod
    def of(cls, dps: DividendPerShare, current_price: float) -> "DividendYield | None":
        if current_price <= 0:
            return None
        return cls(round(dps.amount / current_price, 4))
