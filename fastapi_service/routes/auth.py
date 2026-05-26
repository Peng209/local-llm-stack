"""注册、登录。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from fastapi_service import auth_utils
from fastapi_service.deps import CurrentUser, DbSession
from fastapi_service.models import User
from fastapi_service.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _user_public(user: User) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, session: DbSession) -> TokenResponse:
    existing = await session.execute(
        select(User).where(User.email == body.email.lower())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="该邮箱已注册")

    user = User(
        email=body.email.lower(),
        password_hash=auth_utils.hash_password(body.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="该邮箱已注册") from None
    await session.refresh(user)

    token = auth_utils.create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=_user_public(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: DbSession) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not auth_utils.verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")

    token = auth_utils.create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=_user_public(user),
    )


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return _user_public(user)
