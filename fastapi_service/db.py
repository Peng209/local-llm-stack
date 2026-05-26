"""异步数据库引擎与会话。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from fastapi_service import config

engine = create_async_engine(
    config.DATABASE_URL,
    echo=config.DB_ECHO,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    from fastapi_service import models as _models  # noqa: F401 — 注册表

    del _models
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
