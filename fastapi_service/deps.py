"""路由依赖：数据库会话、JWT 用户、内部 API Key。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from fastapi_service import config
from fastapi_service.auth_utils import decode_access_token
from fastapi_service.db import get_session
from fastapi_service.models import User

_INTERNAL_KEY = config.INTERNAL_API_KEY
_api_key_header = APIKeyHeader(name="X-Internal-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_session)]


def verify_internal_api_key(
    x_internal_key: Annotated[str | None, Security(_api_key_header)],
) -> None:
    if _INTERNAL_KEY and x_internal_key != _INTERNAL_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )


async def get_current_user(
    session: DbSession,
    creds: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或令牌无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(creds.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
