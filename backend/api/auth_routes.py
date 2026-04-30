"""Auth endpoints: bootstrap first admin, login, logout, session (cookie session)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.repositories import user_repository
from backend.repositories.user_repository import UserAlreadyExistsError

auth_router = APIRouter(prefix="/api/auth")


class LoginBody(BaseModel):
    username: str = Field(
        ...,
        min_length=user_repository.MIN_USERNAME_LEN,
        max_length=user_repository.MAX_USERNAME_LEN,
    )
    password: str = Field(..., min_length=user_repository.MIN_PASSWORD_LEN)

    model_config = {"extra": "forbid"}


def _set_session(request: Request, user: dict[str, object]) -> None:
    request.session["authenticated"] = True
    request.session["user_id"] = int(user["id"])
    request.session["username"] = str(user["username"])
    request.session["is_admin"] = bool(user["is_admin"])


def _session_membership_payload(request: Request) -> dict[str, object]:
    sess = request.session
    user_repository.ensure_anon_principal(sess)
    tier = user_repository.effective_tier_for_session(sess)
    pk = user_repository.principal_key_for_session(sess)
    used = user_repository.get_report_usage_today(pk, tier)
    limit = user_repository.daily_limit_for_tier(tier)
    return {
        "membership_tier": tier,
        "report_daily_limit": limit,
        "report_used_today": used,
        "valuation_allowed": tier == user_repository.TIER_PREMIUM,
    }


@auth_router.get("/session")
async def auth_session(request: Request) -> dict:
    n = user_repository.count_users()
    needs_bootstrap = n == 0
    auth_required = n > 0
    base = {
        "auth_enabled": n > 0,
        "auth_required": auth_required,
        "needs_bootstrap": needs_bootstrap,
        **_session_membership_payload(request),
    }
    if request.session.get("authenticated") and request.session.get("username"):
        return {
            **base,
            "authenticated": True,
            "username": str(request.session["username"]),
            "is_admin": bool(request.session.get("is_admin")),
        }
    return {
        **base,
        "authenticated": False,
        "username": None,
        "is_admin": False,
    }


@auth_router.post("/bootstrap")
async def bootstrap(request: Request, body: LoginBody) -> dict:
    if user_repository.count_users() > 0:
        raise HTTPException(status_code=403, detail="Users already exist")
    try:
        user_repository.create_user(
            body.username,
            body.password,
            is_admin=True,
            membership_tier=user_repository.TIER_PREMIUM,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail="Username already exists") from e
    user = user_repository.verify_user(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=500, detail="Bootstrap verification failed")
    _set_session(request, user)
    return {"ok": True}


@auth_router.post("/login")
async def login(request: Request, body: LoginBody) -> dict:
    if user_repository.count_users() == 0:
        raise HTTPException(
            status_code=400,
            detail="No users yet; use POST /api/auth/bootstrap first",
        )
    user = user_repository.verify_user(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    _set_session(request, user)
    return {"ok": True}


@auth_router.post("/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}
