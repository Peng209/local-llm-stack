"""FastAPI 入口：推理 API + React 静态站点。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fastapi_service import config, inference  # noqa: F401 — 加载 .env
from fastapi_service.db import init_db
from fastapi_service.routes.auth import router as auth_router
from fastapi_service.routes.conversations import router as conversations_router
from fastapi_service.routes.web import router as web_router

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
_LOG = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _LOG.info("初始化数据库…")
    await init_db()
    _LOG.info("数据库就绪")
    if config.VLLM_PRELOAD_AT_STARTUP:
        _LOG.info("vLLM 已在 server 入口预加载")
    else:
        _LOG.info("vLLM 将在首次对话时加载")
    yield


app = FastAPI(
    title="my-vllm",
    version="2.1.0",
    description="FastAPI + React 聊天前端；本进程 vLLM 推理；PostgreSQL 持久化。",
    openapi_tags=[
        {"name": "Auth", "description": "注册 / 登录"},
        {"name": "Conversations", "description": "对话 CRUD"},
        {"name": "Web", "description": "浏览器 /api/*"},
        {"name": "Service", "description": "健康检查"},
    ],
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(web_router)


@app.get("/health", tags=["Service"], summary="健康检查")
async def health() -> dict[str, str | None]:
    body: dict[str, str | None] = {
        "status": "ok",
        "model": config.VLLM_MODEL,
        **inference.engine_status(),
    }
    return body


def _mount_frontend() -> None:
    if not FRONTEND_DIST.is_dir():
        return
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404)
        if full_path == "health":
            raise HTTPException(status_code=404)
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")


_mount_frontend()
