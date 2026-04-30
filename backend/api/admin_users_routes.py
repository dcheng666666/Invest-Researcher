"""Admin-only user management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.api.deps import require_admin, require_session_authenticated
from backend.repositories import user_repository
from backend.repositories.user_repository import UserAlreadyExistsError

admin_users_router = APIRouter(
    prefix="/api/admin",
    dependencies=[
        Depends(require_session_authenticated),
        Depends(require_admin),
    ],
)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    membership_tier: str
    created_at: str


class UsersListResponse(BaseModel):
    users: list[UserOut]


class CreateUserBody(BaseModel):
    username: str = Field(
        ...,
        min_length=user_repository.MIN_USERNAME_LEN,
        max_length=user_repository.MAX_USERNAME_LEN,
    )
    password: str = Field(..., min_length=user_repository.MIN_PASSWORD_LEN)
    is_admin: bool = False
    membership_tier: str = user_repository.TIER_NONE

    model_config = {"extra": "forbid"}


class UpdateUserBody(BaseModel):
    membership_tier: str | None = None
    is_admin: bool | None = None
    password: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("password")
    @classmethod
    def password_min_len(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) < user_repository.MIN_PASSWORD_LEN:
            raise ValueError(
                f"Password must be at least {user_repository.MIN_PASSWORD_LEN} characters"
            )
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdateUserBody:
        if (
            self.membership_tier is None
            and self.is_admin is None
            and self.password is None
        ):
            raise ValueError(
                "At least one of membership_tier, is_admin, or password must be set"
            )
        return self


def _user_out_or_404(user_id: int) -> UserOut:
    row = user_repository.get_user_by_id(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**row)


@admin_users_router.get("/users", response_model=UsersListResponse)
async def list_users() -> UsersListResponse:
    rows = user_repository.list_users()
    return UsersListResponse(users=[UserOut(**r) for r in rows])


@admin_users_router.post("/users", response_model=UserOut)
async def create_user(body: CreateUserBody) -> UserOut:
    try:
        tier = user_repository.normalize_membership_tier(body.membership_tier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        uid = user_repository.create_user(
            body.username,
            body.password,
            is_admin=body.is_admin,
            membership_tier=tier,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail="Username already exists") from e
    rows = user_repository.list_users()
    for r in rows:
        if int(r["id"]) == uid:
            return UserOut(**r)
    raise HTTPException(status_code=500, detail="User created but not found")


@admin_users_router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UpdateUserBody) -> UserOut:
    row = user_repository.get_user_by_id(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.is_admin is False and bool(row["is_admin"]):
        if user_repository.count_admins() <= 1:
            raise HTTPException(
                status_code=400,
                detail="无法取消唯一管理员的管理员权限",
            )

    patch: dict[str, object] = {}
    if body.membership_tier is not None:
        try:
            patch["membership_tier"] = user_repository.normalize_membership_tier(
                body.membership_tier
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if body.is_admin is not None:
        patch["is_admin"] = body.is_admin
    if body.password is not None:
        patch["password"] = body.password

    try:
        updated = user_repository.update_user(user_id, **patch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out_or_404(user_id)


@admin_users_router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int) -> Response:
    row = user_repository.get_user_by_id(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    if bool(row["is_admin"]) and user_repository.count_admins() <= 1:
        raise HTTPException(
            status_code=400,
            detail="无法删除唯一的管理员账号",
        )
    if not user_repository.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return Response(status_code=204)
