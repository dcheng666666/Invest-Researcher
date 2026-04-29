"""Security-level static attributes (low-frequency change)."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Profile"]


@dataclass(frozen=True)
class Profile:
    """Static attributes that belong to the **security** itself.

    Company-level attributes (industry, region) live on ``Company``.
    Venue-level attributes (currency) live on ``Exchange``. This object
    only holds what is intrinsic to the security: its display name,
    listing date, and the kind of security it is.
    """

    name: str
    list_date: str | None = None
    security_type: str = "stock"
