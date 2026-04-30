"""Shared FastAPI dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from backend.repositories import user_repository


@dataclass(frozen=True)
class MembershipContext:
    principal_key: str
    tier: str
    valuation_allowed: bool


async def get_membership_context(request: Request) -> MembershipContext:
    sess = request.session
    user_repository.ensure_anon_principal(sess)
    pk = user_repository.principal_key_for_session(sess)
    tier = user_repository.effective_tier_for_session(sess)
    return MembershipContext(
        principal_key=pk,
        tier=tier,
        valuation_allowed=tier == user_repository.TIER_PREMIUM,
    )


async def require_valuation_premium(
    m: Annotated[MembershipContext, Depends(get_membership_context)],
) -> None:
    if not m.valuation_allowed:
        raise HTTPException(
            status_code=403,
            detail="估值筛选仅对高级会员开放。",
        )


async def require_login_when_users_exist(request: Request) -> None:
    """Require a valid session when at least one user account exists (default product policy)."""
    if user_repository.count_users() == 0:
        return
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")


async def require_session_authenticated(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")


async def require_admin(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
