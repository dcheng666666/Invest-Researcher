"""Company entity: the issuer behind one or more securities."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Company"]


@dataclass(frozen=True)
class Company:
    """The legal entity issuing securities.

    Modeled as an entity because one company can list multiple securities
    (A+H pairs, multiple share classes). Identity is currently keyed on
    ``legal_name`` since we have no upstream company id.
    """

    legal_name: str
    industry: str | None = None
    region: str | None = None
